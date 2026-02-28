import { describe, it, expect } from "vitest";
import { verifySignature, handleWebhook } from "../src/webhook.js";

describe("verifySignature", () => {
  const SECRET = "test-secret-key";

  async function sign(secret, body) {
    const key = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(secret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    );
    const mac = await crypto.subtle.sign(
      "HMAC",
      key,
      new TextEncoder().encode(body)
    );
    const hex = Array.from(new Uint8Array(mac))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
    return `sha256=${hex}`;
  }

  it("accepts a valid signature", async () => {
    const body = '{"action":"opened"}';
    const signature = await sign(SECRET, body);
    const result = await verifySignature(SECRET, signature, body);
    expect(result).toBe(true);
  });

  it("rejects an invalid signature", async () => {
    const body = '{"action":"opened"}';
    const signature = "sha256=deadbeef" + "0".repeat(56);
    const result = await verifySignature(SECRET, signature, body);
    expect(result).toBe(false);
  });

  it("rejects missing signature", async () => {
    const result = await verifySignature(SECRET, null, "body");
    expect(result).toBe(false);
  });

  it("rejects empty signature", async () => {
    const result = await verifySignature(SECRET, "", "body");
    expect(result).toBe(false);
  });

  it("rejects signature without sha256= prefix", async () => {
    const result = await verifySignature(SECRET, "abc123", "body");
    expect(result).toBe(false);
  });

  it("rejects when body is tampered", async () => {
    const body = '{"action":"opened"}';
    const signature = await sign(SECRET, body);
    const result = await verifySignature(SECRET, signature, body + "tampered");
    expect(result).toBe(false);
  });

  it("rejects when secret differs", async () => {
    const body = '{"action":"opened"}';
    const signature = await sign("wrong-secret", body);
    const result = await verifySignature(SECRET, signature, body);
    expect(result).toBe(false);
  });
});

describe("handleWebhook", () => {
  it("returns 500 when WEBHOOK_SECRET is not configured", async () => {
    const request = new Request("https://sentinel.example.com/webhook", {
      method: "POST",
      body: "{}",
    });

    const response = await handleWebhook(request, {});
    expect(response.status).toBe(500);
    const text = await response.text();
    expect(text).toBe("Server misconfigured");
  });

  it("returns 500 when WEBHOOK_SECRET is empty string", async () => {
    const request = new Request("https://sentinel.example.com/webhook", {
      method: "POST",
      body: "{}",
    });

    const response = await handleWebhook(request, { WEBHOOK_SECRET: "" });
    expect(response.status).toBe(500);
  });
});
