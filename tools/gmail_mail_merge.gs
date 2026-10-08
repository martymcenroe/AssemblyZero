/**
 * Gmail mail merge run from a Google Sheet (ADR 0238, #4143).
 *
 * Paste into Extensions > Apps Script of the Google Sheet that holds the
 * recipient list, set TEMPLATE_SUBJECT below, save, and reload the sheet.
 * Each project's runbook gives its own setup and runs (ADR 0238).
 *
 * The template is a Gmail draft. Its subject and body may use {{Column}}
 * placeholders named by the sheet's header row ({{FirstName}}, {{Intro}}, ...).
 * The draft's attachments go with every message. Each sent row gets a
 * timestamp in "Email Sent", and a row that already has one is skipped, so the
 * merge can be run again and again as rows are added.
 *
 * Nothing here stores a password or token: the script runs inside the
 * operator's own Google account and sends as him.
 */

// The subject of the Gmail draft used as the template. Change this line to use another draft.
const TEMPLATE_SUBJECT = 'SET THIS TO THE DRAFT SUBJECT';
const RECIPIENT_COL = 'Email';
const SENT_COL = 'Email Sent';

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Mail merge')
    .addItem('Send test to me', 'sendTestToMe')
    .addItem('Send emails', 'sendEmails')
    .addToUi();
}

/** Fill the first unsent row and send it to the operator only. Stamps nothing. */
function sendTestToMe() {
  const job = prepare_();
  if (!job) return;
  const row = job.rows.find((r) => !r[SENT_COL]);
  if (!row) {
    SpreadsheetApp.getUi().alert('Every row is already marked sent.');
    return;
  }
  const me = Session.getActiveUser().getEmail();
  const msg = fill_(job.template, row);
  GmailApp.sendEmail(me, '[TEST to ' + row[RECIPIENT_COL] + '] ' + msg.subject, msg.text, {
    htmlBody: msg.html,
    attachments: job.attachments,
  });
  toast_('Test for ' + row[RECIPIENT_COL] + ' sent to ' + me + '.');
}

/** Send to every unsent row, stamping each as it goes. */
function sendEmails() {
  const job = prepare_();
  if (!job) return;
  const pending = job.rows.filter((r) => !r[SENT_COL]);
  const ui = SpreadsheetApp.getUi();
  const quota = MailApp.getRemainingDailyQuota();
  const answer = ui.alert(
    'Send ' + pending.length + ' emails? (daily quota left: ' + quota + ')',
    ui.ButtonSet.OK_CANCEL,
  );
  if (answer !== ui.Button.OK) return;

  const sentCol = job.header.indexOf(SENT_COL) + 1;
  let sent = 0;
  job.rows.forEach((row, i) => {
    if (row[SENT_COL]) return;
    if (sent >= quota) return;
    try {
      const msg = fill_(job.template, row);
      GmailApp.sendEmail(row[RECIPIENT_COL], msg.subject, msg.text, {
        htmlBody: msg.html,
        attachments: job.attachments,
      });
      job.sheet.getRange(i + 2, sentCol).setValue(new Date());
      sent += 1;
    } catch (e) {
      job.sheet.getRange(i + 2, sentCol).setValue('ERROR: ' + e.message);
    }
    SpreadsheetApp.flush();
  });
  toast_('Sent ' + sent + ' of ' + pending.length + '. Run again to continue if any are left.');
}

/** A notice in the sheet's corner that does not wait for a click. */
function toast_(text) {
  SpreadsheetApp.getActive().toast(text, 'Mail merge', 30);
}

/** The one draft whose subject is TEMPLATE_SUBJECT, found by a Gmail search. */
function findDraft_() {
  const threads = GmailApp.search('in:drafts subject:"' + TEMPLATE_SUBJECT + '"');
  const drafts = [];
  threads.forEach((t) =>
    t.getMessages().forEach((m) => {
      if (m.isDraft() && m.getSubject() === TEMPLATE_SUBJECT) drafts.push(m);
    }),
  );
  return drafts;
}

function prepare_() {
  const ui = SpreadsheetApp.getUi();
  const subject = TEMPLATE_SUBJECT;
  if (subject.indexOf('SET THIS') === 0) {
    ui.alert('Set TEMPLATE_SUBJECT at the top of the script to the Gmail draft\'s subject, then save.');
    return null;
  }

  const drafts = findDraft_();
  if (drafts.length !== 1) {
    ui.alert('Found ' + drafts.length + ' drafts with the subject "' + subject + '"; need exactly one.');
    return null;
  }
  const draft = drafts[0];

  const sheet = SpreadsheetApp.getActiveSheet();
  const values = sheet.getDataRange().getDisplayValues();
  const header = values[0];
  if (header.indexOf(RECIPIENT_COL) < 0 || header.indexOf(SENT_COL) < 0) {
    ui.alert('The sheet needs "' + RECIPIENT_COL + '" and "' + SENT_COL + '" columns.');
    return null;
  }
  const rows = values.slice(1).map((r) => Object.fromEntries(header.map((h, i) => [h, r[i]])));

  return {
    sheet: sheet,
    header: header,
    rows: rows,
    attachments: draft.getAttachments({ includeInlineImages: false }),
    template: { subject: subject, text: draft.getPlainBody(), html: draft.getBody() },
  };
}

function fill_(template, row) {
  const sub = (s) => s.replace(/{{([^}]+)}}/g, (_, key) => (key.trim() in row ? row[key.trim()] : ''));
  return { subject: sub(template.subject), text: sub(template.text), html: sub(template.html) };
}
