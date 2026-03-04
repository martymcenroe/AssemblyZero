The file already exists and the LLD specifies "Verify" (no changes). Here's the complete file:

```typescript
import { test, expect } from "@playwright/test";

/**
 * Conversation detail page tests (React dashboard).
 *
 * Hermes issue #56: Covers:
 * - Back button stale data regression
 * - Deep link ?conv=ID
 * - Conversation metadata display
 * - Label management
 * - Rating interactions
 * - Message display
 *
 * Auth: Uses ?key= query param for owner access.
 */

const AUTH_KEY = process.env.DASHBOARD_API_KEY || "test-key";

function dashboardURL(path = "/conversations"): string {
  return `${path}?key=${AUTH_KEY}`;
}

async function waitForDashboard(page: import("@playwright/test").Page) {
  await page.getByRole("heading", { name: "Hermes Dashboard" }).waitFor({ timeout: 15_000 });
}

/** Navigate to the first conversation's detail page. Returns the conv ID or null if no conversations. */
async function navigateToFirstConversation(page: import("@playwright/test").Page): Promise<string | null> {
  await page.goto(dashboardURL("/conversations"));
  await waitForDashboard(page);

  const firstRow = page.locator("table tbody tr").first();
  const hasConversations = await firstRow
    .waitFor({ timeout: 5_000 })
    .then(() => true)
    .catch(() => false);

  if (!hasConversations) return null;

  // Get the ID from the first cell
  const idText = await page.locator("table tbody tr td").first().textContent();
  const convId = idText?.trim();
  if (!convId) return null;

  await firstRow.click();
  await expect(page).toHaveURL(/\/conversations\/\d+/);
  await expect(page.getByText(`Conversation #${convId}`)).toBeVisible({ timeout: 5_000 });

  return convId;
}

// ---------------------------------------------------------------------------
// Suite 1: Conversation detail metadata
// ---------------------------------------------------------------------------
test.describe("Conversation detail metadata", () => {
  test("shows conversation metadata fields", async ({ page }) => {
    const convId = await navigateToFirstConversation(page);
    if (!convId) {
      test.skip();
      return;
    }

    // Core metadata fields should be visible
    await expect(page.getByText("Sender:")).toBeVisible();
    await expect(page.getByText("Subject:")).toBeVisible();
    await expect(page.getByText("State:")).toBeVisible();
    await expect(page.getByText("Channel:")).toBeVisible();
    await expect(page.getByText("Created:")).toBeVisible();
    await expect(page.getByText("Star:")).toBeVisible();
  });

  test("shows management toggle for owner", async ({ page }) => {
    const convId = await navigateToFirstConversation(page);
    if (!convId) {
      test.skip();
      return;
    }

    // Owner should see management toggle
    await expect(page.getByText("Management:")).toBeVisible();
    const toggleButton = page.getByRole("button", { name: /Take Over|Release to AI/ });
    await expect(toggleButton).toBeVisible();
  });

  test("shows star check for owner", async ({ page }) => {
    const convId = await navigateToFirstConversation(page);
    if (!convId) {
      test.skip();
      return;
    }

    await expect(page.getByText("Check Star:")).toBeVisible();
    await expect(page.getByPlaceholder("GitHub username")).toBeVisible();
    await expect(page.getByRole("button", { name: "Verify" })).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Suite 2: Back button navigation
// ---------------------------------------------------------------------------
test.describe("Back button navigation", () => {
  test("back button returns to conversation list", async ({ page }) => {
    const convId = await navigateToFirstConversation(page);
    if (!convId) {
      test.skip();
      return;
    }

    // Click the Back button
    await page.getByRole("button", { name: /Back/ }).click();

    // Should navigate back to conversation list
    await expect(page).toHaveURL(/\/conversations(\?|$)/);

    // Table should be visible with data
    await expect(page.locator("table")).toBeVisible({ timeout: 5_000 });
    const rows = page.locator("table tbody tr");
    await expect(rows.first()).toBeVisible({ timeout: 5_000 });
  });

  test("back button shows fresh data (not stale)", async ({ page }) => {
    const convId = await navigateToFirstConversation(page);
    if (!convId) {
      test.skip();
      return;
    }

    // Track API calls on back navigation
    const apiCalls: string[] = [];
    page.on("request", (req) => {
      if (req.url().includes("/api/conversations") && !req.url().includes(`/${convId}`)) {
        apiCalls.push(req.url());
      }
    });

    // Click Back
    await page.getByRole("button", { name: /Back/ }).click();
    await expect(page).toHaveURL(/\/conversations(\?|$)/);

    // Wait for refetch
    await page.waitForTimeout(1_000);

    // React Query should have refetched the conversation list
    expect(apiCalls.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// Suite 3: Messages display
// ---------------------------------------------------------------------------
test.describe("Messages display", () => {
  test("messages section shows message history", async ({ page }) => {
    const convId = await navigateToFirstConversation(page);
    if (!convId) {
      test.skip();
      return;
    }

    // Messages heading should be present
    await expect(page.getByRole("heading", { name: "Messages" })).toBeVisible();

    // Should have at least one message bubble (inbound or outbound)
    const messages = page.locator("div.rounded-lg.p-3");
    const messageCount = await messages.count();
    expect(messageCount).toBeGreaterThan(0);
  });

  test("message bubbles show metadata", async ({ page }) => {
    const convId = await navigateToFirstConversation(page);
    if (!convId) {
      test.skip();
      return;
    }

    // First message should show direction and timestamp
    const firstMessage = page.locator("div.rounded-lg.p-3").first();
    const metaText = await firstMessage.locator("div").first().textContent();

    // Metadata should include INBOUND or OUTBOUND and a date
    expect(metaText).toMatch(/INBOUND|OUTBOUND/);
  });
});

// ---------------------------------------------------------------------------
// Suite 4: Labels
// ---------------------------------------------------------------------------
test.describe("Label management", () => {
  test("labels section is visible", async ({ page }) => {
    const convId = await navigateToFirstConversation(page);
    if (!convId) {
      test.skip();
      return;
    }

    await expect(page.getByText("Labels:")).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Suite 5: Compose (owner)
// ---------------------------------------------------------------------------
test.describe("Compose reply", () => {
  test("compose form is visible for owner", async ({ page }) => {
    const convId = await navigateToFirstConversation(page);
    if (!convId) {
      test.skip();
      return;
    }

    // Compose section should be visible
    await expect(page.getByText("Compose Reply")).toBeVisible();
    await expect(page.getByPlaceholder("Type your message...")).toBeVisible();
    await expect(page.getByRole("button", { name: "Send Email" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Attach Files" })).toBeVisible();
  });

  test("empty message shows error toast", async ({ page }) => {
    const convId = await navigateToFirstConversation(page);
    if (!convId) {
      test.skip();
      return;
    }

    // Click Send Email without typing anything
    await page.getByRole("button", { name: "Send Email" }).click();

    // Should show error toast
    await expect(page.getByText("Message body is empty")).toBeVisible({ timeout: 3_000 });
  });
});

// ---------------------------------------------------------------------------
// Suite 6: Rating interactions
// ---------------------------------------------------------------------------
test.describe("Rating interactions", () => {
  test("outbound messages show rating buttons", async ({ page }) => {
    const convId = await navigateToFirstConversation(page);
    if (!convId) {
      test.skip();
      return;
    }

    // Look for outbound messages (they have rating buttons)
    const outboundMessages = page.locator("div.rounded-lg.p-3").filter({
      hasText: /OUTBOUND/,
    });

    const hasOutbound = await outboundMessages
      .first()
      .waitFor({ timeout: 3_000 })
      .then(() => true)
      .catch(() => false);

    if (!hasOutbound) {
      test.skip();
      return;
    }

    // Rating buttons should be inside outbound message bubbles
    // They use emoji labels for 1-5 rating
    const ratingButtons = outboundMessages.first().locator("button.rounded-md");
    const buttonCount = await ratingButtons.count();
    expect(buttonCount).toBeGreaterThanOrEqual(5);
  });
});

// ---------------------------------------------------------------------------
// Suite 7: History toggle
// ---------------------------------------------------------------------------
test.describe("History toggle", () => {
  test("show full history button appears when conversation has reinits", async ({ page }) => {
    const convId = await navigateToFirstConversation(page);
    if (!convId) {
      test.skip();
      return;
    }

    // The "Show Full History" button only appears if last_init_at is set
    const historyButton = page.getByRole("button", { name: /Show Full History|Show Recent Only/ });
    const hasHistory = await historyButton
      .waitFor({ timeout: 2_000 })
      .then(() => true)
      .catch(() => false);

    // This test just confirms the button renders when appropriate — skip if no reinits
    if (!hasHistory) {
      test.skip();
      return;
    }

    await expect(historyButton).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Suite 8: Delete button
// ---------------------------------------------------------------------------
test.describe("Delete conversation", () => {
  test("delete button is visible for owner", async ({ page }) => {
    const convId = await navigateToFirstConversation(page);
    if (!convId) {
      test.skip();
      return;
    }

    await expect(page.getByRole("button", { name: /Delete/ }).first()).toBeVisible();
  });

  // Note: We intentionally do NOT test the actual delete action in E2E
  // since it's destructive and affects real data.
});
```
