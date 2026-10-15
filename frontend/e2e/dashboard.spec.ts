import { expect, request as playwrightRequest, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const password = "browser-test-password";

async function register(page: Page, email: string) {
	await page.goto("/");
	await expect(page.getByText("Sign in to SearchIntel")).toBeVisible();
	await page.getByRole("button", { name: /create an account/i }).click();
	await page.getByLabel("Email").fill(email);
	await page.getByLabel("Password").fill(password);
	await page.getByRole("button", { name: "Create account", exact: true }).click();
	await expect(page.getByText("Good morning")).toBeVisible({ timeout: 15_000 });
}

test("user can register, crawl, audit, browse pages, and ask a cited RAG question", async ({ page }) => {
	const email = `e2e-${Date.now()}@example.com`;
	await register(page, email);

	await page.getByRole("button", { name: "New project" }).click();
	await page.getByLabel("Project name").fill("Browser E2E project");
	await page.getByLabel("Primary website (optional)").fill("http://127.0.0.1:18888/");
	await page.getByRole("button", { name: "Create project" }).click();
	await expect(page.getByLabel("Website")).toContainText("127.0.0.1");

	await page.getByRole("button", { name: "Start crawl" }).click();
	await expect(page.getByText("Crawl completed", { exact: true })).toBeVisible({ timeout: 30_000 });
	await expect(page.getByText("2 pages", { exact: true })).toBeVisible();
	await expect(page.getByText("Indexed pages", { exact: true })).toBeVisible();
	await expect(page.getByText("SearchIntel Test Home", { exact: true })).toBeVisible();

	await page.getByRole("button", { name: "Run SEO audit" }).click();
	await expect(page.getByText("COMPLETED", { exact: true })).toBeVisible({ timeout: 30_000 });
	await expect(page.getByText("TITLE_MISSING", { exact: true })).toBeVisible();

	await page.getByPlaceholder("What does my site say about…").fill("What does the homepage describe?");
	await page.getByRole("button", { name: "Ask question" }).click();
	await expect(page.getByText("SOURCES", { exact: true })).toBeVisible({ timeout: 15_000 });
	await expect(page.getByRole("link", { name: /\[1\]/ })).toBeVisible();

	await page.getByRole("button", { name: "Add website" }).click();
	await page.getByLabel("Website URL").fill("http://localhost:18889/");
	await page.getByLabel("Website role").selectOption("COMPETITOR");
	await page.getByRole("button", { name: "Register website" }).click();
	await page.getByLabel("Website").selectOption({ label: "localhost · competitor" });
	await page.getByRole("button", { name: "Start crawl" }).click();
	await expect(page.getByText("Crawl completed", { exact: true })).toBeVisible({ timeout: 30_000 });
	await expect(page.getByText("Competitor content coverage", { exact: true })).toBeVisible();
	await page.getByRole("button", { name: "Refresh" }).last().click();
	await expect(page.getByText("quantum", { exact: true })).toBeVisible();
});

test("tenant authorization blocks outsiders and dashboard reports network failures", async ({ page }) => {
	const ownerEmail = `owner-${Date.now()}@example.com`;
	await register(page, ownerEmail);
	const tenantId = await page.locator('select[aria-label="Workspace"]').inputValue();

	const outsider = await playwrightRequest.newContext({ baseURL: page.url() });
	const outsiderEmail = `outsider-${Date.now()}@example.com`;
	const registration = await outsider.post("/api-proxy/auth/register", {
		data: { email: outsiderEmail, password },
	});
	expect(registration.status()).toBe(201);
	const login = await outsider.post("/api-proxy/auth/login", {
		form: { username: outsiderEmail, password },
	});
	expect(login.status()).toBe(204);
	const state = await outsider.storageState();
	const csrf = state.cookies.find((cookie) => cookie.name === "searchintel_csrf")?.value;
	const foreignTenant = await outsider.post("/api-proxy/tenants", {
		data: { name: "Outsider workspace" },
		headers: { "X-CSRF-Token": csrf ?? "" },
	});
	expect(foreignTenant.status()).toBe(201);
	const foreignTenantBody = (await foreignTenant.json()) as { id: string };
	const protectedRead = await page.evaluate(async (foreignTenantId) => {
		const response = await fetch(`/api-proxy/projects?tenant_id=${encodeURIComponent(foreignTenantId)}`);
		return response.status;
	}, foreignTenantBody.id);
	expect(protectedRead).toBe(404);
	await outsider.dispose();

	await page.route("**/api-proxy/projects?*", (route) => route.abort("failed"));
	await page.reload();
	await expect(page.getByRole("alert")).toBeVisible({ timeout: 15_000 });
	expect(tenantId).toBeTruthy();
});

test("Redis-backed login throttling returns Retry-After when the configured limit is reached", async ({ page }) => {
	await page.goto("/");
	const client = await playwrightRequest.newContext({ baseURL: page.url() });
	let limited = false;
	for (let attempt = 0; attempt < 12; attempt += 1) {
		const response = await client.post("/api-proxy/auth/login", {
			form: { username: `invalid-${attempt}@example.com`, password: "invalid-password" },
		});
		if (response.status() === 429) {
			expect(Number(response.headers()["retry-after"])).toBeGreaterThan(0);
			limited = true;
			break;
		}
	}
	expect(limited).toBe(true);
	await client.dispose();
});
