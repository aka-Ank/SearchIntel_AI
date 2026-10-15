"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
	Activity,
	ArrowUpRight,
	Bot,
	Check,
	CircleHelp,
	Clock3,
	FileSearch,
	Globe2,
	Layers3,
	LoaderCircle,
	Plus,
	Search,
	Send,
	ShieldCheck,
	Sparkles,
	X,
} from "lucide-react";

type Project = {
	id: string;
	tenant_id: string;
	name: string;
	website_url?: string | null;
	competitor_urls: string[];
};
type Website = {
	id: string;
	tenant_id: string;
	project_id: string;
	base_url: string;
	domain: string;
	website_type: "OWN" | "COMPETITOR";
};
type PageItem = {
	id: string;
	website_id: string;
	url: string;
	title?: string | null;
	status_code?: number;
	word_count: number;
	crawled_at: string;
};
type CrawlJob = {
	id: string;
	status: string;
	pages_discovered: number;
	pages_queued: number;
	pages_processed: number;
	pages_crawled: number;
	pages_failed: number;
	error_message?: string | null;
};
type AuditRun = {
	id: string;
	status: string;
	pages_total: number;
	pages_processed: number;
	error_message?: string | null;
};
type Finding = {
	id: string;
	page_id?: string | null;
	rule_id: string;
	severity: string;
	affected_url: string;
	explanation: string;
	evidence: Record<string, unknown>;
	recommended_action: string;
};
type Citation = {
	citation_number: number;
	page_title?: string | null;
	url: string;
	page_id: string;
	supporting_snippet: string;
};
type RagResponse = { answer: string; citations: Citation[]; grounded: boolean };

const API = "/api-proxy";
async function request<T>(path: string, init?: RequestInit): Promise<T> {
	const response = await fetch(`${API}${path}`, {
		...init,
		headers: { "Content-Type": "application/json", ...init?.headers },
	});
	if (!response.ok) {
		const body = await response.json().catch(() => null);
		const message = body?.detail ?? `Request failed (${response.status})`;
		throw new Error(
			typeof message === "string" ? message : JSON.stringify(message),
		);
	}
	return response.json() as Promise<T>;
}

const isActive = (status?: string) =>
	status === "PENDING" || status === "RUNNING" || status === "CANCEL_REQUESTED";
const shortDate = (value: string) =>
	new Intl.DateTimeFormat(undefined, {
		dateStyle: "medium",
		timeStyle: "short",
	}).format(new Date(value));

export default function Dashboard() {
	const [tenant, setTenant] = useState("local-tenant");
	const [tenantDraft, setTenantDraft] = useState("local-tenant");
	const [projects, setProjects] = useState<Project[]>([]);
	const [projectId, setProjectId] = useState("");
	const [websites, setWebsites] = useState<Website[]>([]);
	const [websiteId, setWebsiteId] = useState("");
	const [pages, setPages] = useState<PageItem[]>([]);
	const [job, setJob] = useState<CrawlJob | null>(null);
	const [audit, setAudit] = useState<AuditRun | null>(null);
	const [findings, setFindings] = useState<Finding[]>([]);
	const [rag, setRag] = useState<RagResponse | null>(null);
	const [question, setQuestion] = useState("");
	const [searchText, setSearchText] = useState("");
	const [query, setQuery] = useState("");
	const [error, setError] = useState("");
	const [busy, setBusy] = useState("");
	const [showProjectForm, setShowProjectForm] = useState(false);
	const [showWebsiteForm, setShowWebsiteForm] = useState(false);
	const [projectName, setProjectName] = useState("");
	const [projectUrl, setProjectUrl] = useState("");
	const [newWebsiteUrl, setNewWebsiteUrl] = useState("");
	const [maxPages, setMaxPages] = useState(50);
	const [apiOnline, setApiOnline] = useState(false);
	const [selectedPage, setSelectedPage] = useState<PageItem | null>(null);
	const [severity, setSeverity] = useState("all");

	const selectedWebsite = websites.find((site) => site.id === websiteId);
	const visibleFindings = useMemo(
		() =>
			severity === "all"
				? findings
				: findings.filter((item) => item.severity === severity),
		[findings, severity],
	);
	const pageMap = useMemo(
		() => new Map(pages.map((page) => [page.id, page])),
		[pages],
	);
	useEffect(() => {
		const savedTenant = window.localStorage.getItem("searchintel.tenant");
		if (savedTenant) {
			setTenant(savedTenant);
			setTenantDraft(savedTenant);
		}
	}, []);

	const loadProjects = useCallback(async () => {
		if (!tenant.trim()) return;
		try {
			const values = await request<Project[]>(
				`/projects?tenant_id=${encodeURIComponent(tenant)}`,
			);
			setProjects(values);
			setApiOnline(true);
			const remembered = window.localStorage.getItem(
				`searchintel.project.${tenant}`,
			);
			setProjectId((current) =>
				values.some((item) => item.id === current)
					? current
					: (values.find((item) => item.id === remembered)?.id ??
						values[0]?.id ??
						""),
			);
		} catch (cause) {
			setApiOnline(false);
			setError(cause instanceof Error ? cause.message : "API is not reachable");
		}
	}, [tenant]);

	const loadWebsiteData = useCallback(
		async (selectedProject: string) => {
			if (!selectedProject) {
				setWebsites([]);
				setPages([]);
				setWebsiteId("");
				return;
			}
			try {
				const [siteRows, pageRows] = await Promise.all([
					request<Website[]>(
						`/projects/${selectedProject}/websites?tenant_id=${encodeURIComponent(tenant)}`,
					),
					request<PageItem[]>(
						`/projects/${selectedProject}/pages?tenant_id=${encodeURIComponent(tenant)}`,
					),
				]);
				setWebsites(siteRows);
				setPages(pageRows);
				const remembered = window.localStorage.getItem(
					`searchintel.website.${tenant}.${selectedProject}`,
				);
				setWebsiteId((current) =>
					siteRows.some((item) => item.id === current)
						? current
						: (siteRows.find((item) => item.id === remembered)?.id ??
							siteRows[0]?.id ??
							""),
				);
			} catch (cause) {
				setError(
					cause instanceof Error
						? cause.message
						: "Could not load website data",
				);
			}
		},
		[tenant],
	);

	useEffect(() => {
		const timer = window.setTimeout(() => {
			void loadProjects();
		}, 0);
		return () => window.clearTimeout(timer);
	}, [loadProjects]);
	useEffect(() => {
		if (projectId)
			window.localStorage.setItem(`searchintel.project.${tenant}`, projectId);
		const timer = window.setTimeout(() => {
			void loadWebsiteData(projectId);
		}, 0);
		return () => window.clearTimeout(timer);
	}, [projectId, tenant, loadWebsiteData]);
	useEffect(() => {
		if (websiteId && projectId)
			window.localStorage.setItem(
				`searchintel.website.${tenant}.${projectId}`,
				websiteId,
			);
	}, [websiteId, projectId, tenant]);
	useEffect(() => {
		if (!websiteId) {
			setJob(null);
			setAudit(null);
			setFindings([]);
			return;
		}
		let canceled = false;
		async function loadHistory() {
			try {
				const suffix = `tenant_id=${encodeURIComponent(tenant)}`;
				const [jobs, audits] = await Promise.all([
					request<CrawlJob[]>(`/websites/${websiteId}/crawl-jobs?${suffix}`),
					request<AuditRun[]>(`/websites/${websiteId}/seo-audits?${suffix}`),
				]);
				if (canceled) return;
				setJob(jobs[0] ?? null);
				const latestAudit = audits[0] ?? null;
				setAudit(latestAudit);
				if (latestAudit?.status === "COMPLETED") {
					const rows = await request<Finding[]>(
						`/seo-audits/${latestAudit.id}/findings?${suffix}`,
					);
					if (!canceled) setFindings(rows);
				} else {
					setFindings([]);
				}
			} catch (cause) {
				if (!canceled) {
					setError(
						cause instanceof Error
							? cause.message
							: "Could not load crawl and audit history",
					);
				}
			}
		}
		void loadHistory();
		return () => {
			canceled = true;
		};
	}, [websiteId, tenant]);

	useEffect(() => {
		if (!job || !isActive(job.status)) return;
		const timer = window.setInterval(async () => {
			try {
				const latest = await request<CrawlJob>(
					`/crawl-jobs/${job.id}?tenant_id=${encodeURIComponent(tenant)}`,
				);
				setJob(latest);
				if (!isActive(latest.status)) {
					await loadWebsiteData(projectId);
				}
			} catch (cause) {
				setError(
					cause instanceof Error
						? cause.message
						: "Could not refresh crawl status",
				);
			}
		}, 1800);
		return () => window.clearInterval(timer);
	}, [job, tenant, projectId, loadWebsiteData]);

	useEffect(() => {
		if (!audit || !isActive(audit.status)) return;
		const timer = window.setInterval(async () => {
			try {
				const latest = await request<AuditRun>(
					`/seo-audits/${audit.id}?tenant_id=${encodeURIComponent(tenant)}`,
				);
				setAudit(latest);
				if (latest.status === "COMPLETED") {
					const rows = await request<Finding[]>(
						`/seo-audits/${audit.id}/findings?tenant_id=${encodeURIComponent(tenant)}`,
					);
					setFindings(rows);
				}
			} catch (cause) {
				setError(
					cause instanceof Error
						? cause.message
						: "Could not refresh audit status",
				);
			}
		}, 1800);
		return () => window.clearInterval(timer);
	}, [audit, tenant]);

	async function createProject(event: React.FormEvent<HTMLFormElement>) {
		event.preventDefault();
		setBusy("project");
		setError("");
		try {
			const created = await request<Project>("/projects", {
				method: "POST",
				body: JSON.stringify({
					tenant_id: tenant,
					name: projectName,
					website_url: projectUrl || null,
				}),
			});
			setProjects((current) => [created, ...current]);
			setProjectId(created.id);
			setShowProjectForm(false);
			setProjectName("");
			setProjectUrl("");
		} catch (cause) {
			setError(
				cause instanceof Error ? cause.message : "Could not create project",
			);
		} finally {
			setBusy("");
		}
	}

	async function addWebsite(event: React.FormEvent<HTMLFormElement>) {
		event.preventDefault();
		if (!projectId) return;
		setBusy("website");
		setError("");
		try {
			const site = await request<Website>(`/projects/${projectId}/websites`, {
				method: "POST",
				body: JSON.stringify({
					tenant_id: tenant,
					base_url: newWebsiteUrl,
					website_type: "OWN",
				}),
			});
			setWebsites((current) => [...current, site]);
			setWebsiteId(site.id);
			setShowWebsiteForm(false);
			setNewWebsiteUrl("");
		} catch (cause) {
			setError(
				cause instanceof Error ? cause.message : "Could not register website",
			);
		} finally {
			setBusy("");
		}
	}

	async function startCrawl() {
		if (!websiteId) return;
		setBusy("crawl");
		setError("");
		try {
			const created = await request<CrawlJob>(`/websites/${websiteId}/crawl`, {
				method: "POST",
				body: JSON.stringify({
					tenant_id: tenant,
					max_pages: maxPages,
					max_depth: 3,
					concurrency: 4,
				}),
			});
			setJob(created);
		} catch (cause) {
			setError(
				cause instanceof Error ? cause.message : "Could not queue crawl",
			);
		} finally {
			setBusy("");
		}
	}

	async function cancelCrawl() {
		if (!job) return;
		try {
			setJob(
				await request<CrawlJob>(
					`/crawl-jobs/${job.id}?tenant_id=${encodeURIComponent(tenant)}`,
					{ method: "DELETE" },
				),
			);
		} catch (cause) {
			setError(
				cause instanceof Error ? cause.message : "Could not cancel crawl",
			);
		}
	}

	async function startAudit() {
		if (!websiteId) return;
		setBusy("audit");
		setError("");
		setFindings([]);
		try {
			setAudit(
				await request<AuditRun>(
					`/websites/${websiteId}/seo-audits?tenant_id=${encodeURIComponent(tenant)}`,
					{ method: "POST" },
				),
			);
		} catch (cause) {
			setError(
				cause instanceof Error ? cause.message : "Could not queue audit",
			);
		} finally {
			setBusy("");
		}
	}

	async function askAssistant(event: React.FormEvent<HTMLFormElement>) {
		event.preventDefault();
		if (!question.trim() || !projectId) return;
		setBusy("rag");
		setError("");
		setRag(null);
		try {
			const answer = await request<RagResponse>("/rag/query", {
				method: "POST",
				body: JSON.stringify({
					tenant_id: tenant,
					project_id: projectId,
					question,
					top_k: 5,
					search_strategy: "hybrid_rerank",
				}),
			});
			setRag(answer);
			setQuestion("");
		} catch (cause) {
			setError(
				cause instanceof Error ? cause.message : "The assistant request failed",
			);
		} finally {
			setBusy("");
		}
	}

	async function runSearch(event: React.FormEvent<HTMLFormElement>) {
		event.preventDefault();
		if (!searchText.trim() || !projectId) return;
		setBusy("search");
		setError("");
		try {
			const response = await request<{
				results: {
					title?: string;
					url: string;
					snippet: string;
					score: number;
				}[];
			}>("/search", {
				method: "POST",
				body: JSON.stringify({
					tenant_id: tenant,
					project_id: projectId,
					query: searchText,
					top_k: 5,
					strategy: "hybrid",
				}),
			});
			setQuery(searchText);
			setSearchResults(response.results);
		} catch (cause) {
			setError(cause instanceof Error ? cause.message : "Search failed");
		} finally {
			setBusy("");
		}
	}

	const [searchResults, setSearchResults] = useState<
		{ title?: string; url: string; snippet: string; score: number }[]
	>([]);
	async function loadAllFindings() {
		if (!audit) return;
		try {
			setFindings(
				await request<Finding[]>(
					`/seo-audits/${audit.id}/findings?tenant_id=${encodeURIComponent(tenant)}`,
				),
			);
		} catch (cause) {
			setError(
				cause instanceof Error ? cause.message : "Could not load findings",
			);
		}
	}

	const activeJob = isActive(job?.status);
	const errorsCount = findings.filter(
		(item) => item.severity === "error",
	).length;
	const warningCount = findings.filter(
		(item) => item.severity === "warning",
	).length;

	return (
		<div className="min-h-screen bg-canvas text-ink">
			<aside className="fixed inset-y-0 left-0 z-20 hidden w-[244px] flex-col border-r border-line bg-white px-5 py-6 lg:flex">
				<div className="mb-10 flex items-center gap-3 px-1">
					<div className="grid h-10 w-10 place-items-center rounded-xl bg-forest text-white">
						<Activity size={20} />
					</div>
					<div>
						<div className="text-[15px] font-bold tracking-tight">
							SearchIntel
						</div>
						<div className="text-[11px] text-muted">WEBSITE INTELLIGENCE</div>
					</div>
				</div>
				<div className="mb-3 px-2 text-[10px] font-semibold uppercase tracking-[.16em] text-muted">
					Workspace
				</div>
				<nav className="space-y-1 text-sm">
					<a
						href="#overview"
						className="flex items-center gap-3 rounded-lg bg-[#edf5f1] px-3 py-2.5 font-semibold text-forest"
					>
						<Layers3 size={17} /> Overview
					</a>
					<a
						href="#crawl"
						className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-[#53615b] hover:bg-canvas"
					>
						<Globe2 size={17} /> Websites & crawls
					</a>
					<a
						href="#audit"
						className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-[#53615b] hover:bg-canvas"
					>
						<FileSearch size={17} /> SEO audits
					</a>
					<a
						href="#assistant"
						className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-[#53615b] hover:bg-canvas"
					>
						<Bot size={17} /> AI assistant
					</a>
				</nav>
				<div className="mt-auto rounded-xl border border-line bg-canvas p-3.5">
					<div className="mb-2 flex items-center gap-2 text-xs font-semibold">
						<ShieldCheck size={15} className="text-forest" /> Local workspace
					</div>
					<div className="text-[11px] leading-relaxed text-muted">
						Use a tenant ID for your local project data. Authentication is not
						configured in this MVP.
					</div>
				</div>
			</aside>

			<main className="lg:pl-[244px]">
				<header className="sticky top-0 z-10 flex h-[68px] items-center justify-between border-b border-line bg-white/95 px-5 backdrop-blur md:px-9">
					<div className="flex min-w-0 items-center gap-3">
						<div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-forest text-white lg:hidden">
							<Activity size={18} />
						</div>
						<div>
							<div className="text-xs text-muted">Workspace / Overview</div>
							<div className="max-w-[42vw] truncate text-sm font-semibold">
								{projects.find((item) => item.id === projectId)?.name ??
									"Your workspace"}
							</div>
						</div>
					</div>
					<div className="flex items-center gap-3">
						<div
							className={`hidden items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] sm:flex ${apiOnline ? "bg-[#eaf5ef] text-forest" : "bg-amber-50 text-amber-700"}`}
						>
							<span
								className={`h-1.5 w-1.5 rounded-full ${apiOnline ? "bg-emerald-500" : "bg-amber-500"}`}
							/>
							{apiOnline ? "API connected" : "API unavailable"}
						</div>
						<div className="hidden items-center gap-2 rounded-lg border border-line bg-white px-2.5 py-1.5 md:flex">
							<span className="text-[11px] text-muted">Tenant</span>
							<input
								aria-label="Tenant ID"
								value={tenantDraft}
								onChange={(event) => setTenantDraft(event.target.value)}
								onBlur={() => {
									const value = tenantDraft.trim();
									if (value) {
										setTenant(value);
										window.localStorage.setItem("searchintel.tenant", value);
										setProjectId("");
										setJob(null);
										setAudit(null);
										setFindings([]);
									}
								}}
								onKeyDown={(event) => {
									if (event.key === "Enter") event.currentTarget.blur();
								}}
								className="w-28 border-0 bg-transparent text-xs outline-none"
							/>
						</div>
						<div className="grid h-8 w-8 place-items-center rounded-full bg-[#dbece4] text-xs font-bold text-forest">
							SI
						</div>
					</div>
				</header>

				<div className="mx-auto max-w-[1440px] px-4 py-7 md:px-9 md:py-9">
					<section
						id="overview"
						className="mb-7 flex flex-col justify-between gap-4 md:flex-row md:items-end"
					>
						<div>
							<div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-[#e9f4ee] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[.13em] text-forest">
								<Sparkles size={12} /> Search intelligence
							</div>
							<h1 className="text-[26px] font-semibold tracking-[-.04em] md:text-[32px]">
								Good morning<span className="text-forest">.</span>
							</h1>
							<p className="mt-1 text-sm text-muted">
								Your site health, crawl activity, and evidence-backed insights.
							</p>
						</div>
						<div className="flex gap-2">
							<button type="button"
								onClick={() => setShowWebsiteForm(true)}
								disabled={!projectId}
								className="inline-flex items-center gap-2 rounded-lg border border-line bg-white px-3.5 py-2.5 text-xs font-semibold shadow-sm hover:bg-canvas"
							>
								<Plus size={15} /> Add website
							</button>
							<button type="button"
								onClick={() => setShowProjectForm(true)}
								className="inline-flex items-center gap-2 rounded-lg bg-forest px-3.5 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-[#17563f]"
							>
								<Plus size={15} /> New project
							</button>
						</div>
					</section>

					{error && (
						<div
							role="alert"
							className="mb-5 flex items-start justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
						>
							<span>{error}</span>
							<button type="button" aria-label="Dismiss error" onClick={() => setError("")}>
								<X size={16} />
							</button>
						</div>
					)}

					<section className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
						<MetricCard
							label="Registered websites"
							value={String(websites.length)}
							helper={selectedWebsite?.domain ?? "Across selected project"}
							icon={<Globe2 size={17} />}
							trend="Connected"
						/>
						<MetricCard
							label="Pages indexed"
							value={String(pages.length)}
							helper="Persisted in this project"
							icon={<Layers3 size={17} />}
							trend={pages.length ? "Ready to explore" : "Waiting for crawl"}
						/>
						<MetricCard
							label="Audit findings"
							value={String(findings.length)}
							helper={`${errorsCount} critical · ${warningCount} warnings`}
							icon={<FileSearch size={17} />}
							trend={audit?.status ?? "No audit loaded"}
						/>
						<MetricCard
							label="Latest crawl"
							value={job?.status ?? "No crawl yet"}
							helper={
								job
									? `${job.pages_crawled} successful · ${job.pages_failed} failed`
									: "Start a crawl to collect pages"
							}
							icon={<Activity size={17} />}
							trend={activeJob ? "In progress" : "Job state"}
						/>
					</section>

					<section className="mb-6 grid gap-5 xl:grid-cols-[1.6fr_1fr]">
						<div
							id="crawl"
							className="rounded-2xl border border-line bg-white p-5 shadow-soft md:p-6"
						>
							<div className="mb-5 flex items-start justify-between gap-4">
								<div>
									<h2 className="text-base font-semibold">Website crawl</h2>
									<p className="mt-1 text-xs text-muted">
										Queue a bounded crawl and watch persisted progress update.
									</p>
								</div>
								<div className="grid h-9 w-9 place-items-center rounded-xl bg-[#edf5f1] text-forest">
									<Globe2 size={18} />
								</div>
							</div>
							<div className="mb-4 grid gap-3 sm:grid-cols-[1fr_120px]">
								<label className="text-[11px] font-medium text-muted">
									Website
									<select
										value={websiteId}
										onChange={(event) => {
											setWebsiteId(event.target.value);
											setJob(null);
											setAudit(null);
											setFindings([]);
										}}
										className="mt-1.5 block h-10 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink outline-none focus:border-forest"
									>
										{websites.length ? (
											websites.map((site) => (
												<option key={site.id} value={site.id}>
													{site.domain} · {site.website_type.toLowerCase()}
												</option>
											))
										) : (
											<option value="">Add a website to begin</option>
										)}
									</select>
								</label>
								<label className="text-[11px] font-medium text-muted">
									Page limit
									<input
										type="number"
										min={1}
										max={500}
										value={maxPages}
										onChange={(event) =>
											setMaxPages(Number(event.target.value))
										}
										className="mt-1.5 block h-10 w-full rounded-lg border border-line px-3 text-sm text-ink outline-none focus:border-forest"
									/>
								</label>
							</div>
							<div className="flex flex-wrap items-center gap-2">
								<button type="button"
									onClick={startCrawl}
									disabled={!websiteId || !!busy || !!activeJob}
									className="inline-flex items-center gap-2 rounded-lg bg-forest px-4 py-2.5 text-xs font-semibold text-white hover:bg-[#17563f]"
								>
									{busy === "crawl" ? (
										<LoaderCircle size={15} className="animate-spin" />
									) : (
										<Activity size={15} />
									)}{" "}
									Start crawl
								</button>
								<button type="button"
									onClick={startAudit}
									disabled={
										!websiteId ||
										!!busy ||
										!!activeJob ||
										isActive(audit?.status)
									}
									className="inline-flex items-center gap-2 rounded-lg border border-line px-4 py-2.5 text-xs font-semibold hover:bg-canvas"
								>
									{busy === "audit" ? (
										<LoaderCircle size={15} className="animate-spin" />
									) : (
										<FileSearch size={15} />
									)}{" "}
									Run SEO audit
								</button>
								{activeJob && (
									<button type="button"
										onClick={cancelCrawl}
										className="rounded-lg px-3 py-2 text-xs font-semibold text-red-700 hover:bg-red-50"
									>
										Cancel crawl
									</button>
								)}
							</div>
							{(job || audit) && (
								<div className="mt-5 rounded-xl bg-canvas p-4">
									<div className="mb-3 flex items-center justify-between">
										<div className="flex items-center gap-2 text-xs font-semibold">
											{activeJob ? (
												<LoaderCircle
													size={15}
													className="animate-spin text-forest"
												/>
											) : (
												<Check size={15} className="text-forest" />
											)}
											{job
												? `Crawl ${job.status.toLowerCase()}`
												: `Audit ${audit?.status.toLowerCase()}`}
										</div>
										<span className="text-[11px] text-muted">
											{job
												? `${job.pages_processed} processed`
												: `${audit?.pages_processed ?? 0} / ${audit?.pages_total ?? 0} pages`}
										</span>
									</div>
									{job && (
										<>
											<div className="h-2 overflow-hidden rounded-full bg-[#e1e8e3]">
												<div
													className="h-full rounded-full bg-forest transition-all"
													style={{
														width: `${Math.min(100, job.pages_discovered ? (job.pages_processed / job.pages_discovered) * 100 : 4)}%`,
													}}
												/>
											</div>
											<div className="mt-3 grid grid-cols-4 gap-2 text-[10px] text-muted">
												<span>{job.pages_discovered} discovered</span>
												<span>{job.pages_queued} queued</span>
												<span>{job.pages_crawled} successful</span>
												<span>{job.pages_failed} failed</span>
											</div>
											{job.error_message && (
												<p className="mt-2 text-xs text-red-700">
													{job.error_message}
												</p>
											)}
										</>
									)}
									{audit?.error_message && (
										<p className="mt-2 text-xs text-red-700">
											{audit.error_message}
										</p>
									)}
								</div>
							)}
						</div>

						<div className="rounded-2xl border border-line bg-white p-5 shadow-soft md:p-6">
							<div className="mb-4 flex items-center justify-between">
								<div>
									<h2 className="text-base font-semibold">Your websites</h2>
									<p className="mt-1 text-xs text-muted">
										Registered under this project.
									</p>
								</div>
								<Globe2 size={17} className="text-muted" />
							</div>
							{websites.length ? (
								<div className="space-y-2">
									{websites.map((site) => (
										<button type="button"
											key={site.id}
											onClick={() => setWebsiteId(site.id)}
											className={`flex w-full items-center gap-3 rounded-xl border p-3 text-left ${site.id === websiteId ? "border-[#bfd9cb] bg-[#f4faf6]" : "border-line hover:bg-canvas"}`}
										>
											<div className="grid h-9 w-9 place-items-center rounded-lg bg-white text-forest">
												<Globe2 size={16} />
											</div>
											<div className="min-w-0 flex-1">
												<div className="truncate text-xs font-semibold">
													{site.domain}
												</div>
												<div className="truncate text-[10px] text-muted">
													{site.base_url}
												</div>
											</div>
											<span className="rounded-full bg-white px-2 py-1 text-[9px] font-semibold text-muted">
												{site.website_type}
											</span>
										</button>
									))}
								</div>
							) : (
								<EmptyState
									title="No websites yet"
									text="Register a domain in this project to start crawling."
									action="Add website"
									onClick={() =>
										projectId
											? setShowWebsiteForm(true)
											: setShowProjectForm(true)
									}
								/>
							)}
						</div>
					</section>

					<section className="mb-6 grid gap-5 xl:grid-cols-[1.4fr_1fr]">
						<div
							id="audit"
							className="rounded-2xl border border-line bg-white p-5 shadow-soft md:p-6"
						>
							<div className="mb-4 flex flex-wrap items-center justify-between gap-3">
								<div>
									<h2 className="text-base font-semibold">
										Technical SEO findings
									</h2>
									<p className="mt-1 text-xs text-muted">
										Deterministic checks with evidence from crawled pages.
									</p>
								</div>
								<div className="flex items-center gap-2">
									<select
										value={severity}
										onChange={(event) => setSeverity(event.target.value)}
										className="rounded-lg border border-line bg-white px-2.5 py-2 text-[11px]"
									>
										<option value="all">All severities</option>
										<option value="error">Errors</option>
										<option value="warning">Warnings</option>
										<option value="info">Info</option>
									</select>
									<button type="button"
										onClick={loadAllFindings}
										disabled={audit?.status !== "COMPLETED"}
										className="rounded-lg border border-line px-3 py-2 text-[11px] font-semibold hover:bg-canvas"
									>
										Refresh
									</button>
								</div>
							</div>
							{audit && (
								<div className="mb-3 flex items-center gap-2 text-[11px] text-muted">
									<span
										className={`rounded-full px-2 py-1 font-semibold ${audit.status === "COMPLETED" ? "bg-[#eaf5ef] text-forest" : "bg-amber-50 text-amber-700"}`}
									>
										{audit.status}
									</span>
									<span>
										{audit.pages_processed} / {audit.pages_total} audited pages
									</span>
									<span className="ml-auto">
										{visibleFindings.length} findings
									</span>
								</div>
							)}
							{visibleFindings.length ? (
								<div className="max-h-[380px] space-y-2 overflow-auto">
									{visibleFindings.map((finding) => (
										<article
											key={finding.id}
											className="rounded-xl border border-line p-3.5"
										>
											<div className="mb-1.5 flex items-center justify-between gap-3">
												<div className="flex items-center gap-2">
													<Severity severity={finding.severity} />
													<code className="text-[10px] font-semibold tracking-wide text-ink">
														{finding.rule_id}
													</code>
												</div>
												<button type="button"
													onClick={() => {
														const page = finding.page_id
															? pageMap.get(finding.page_id)
															: null;
														if (page) setSelectedPage(page);
													}}
													className="truncate text-right text-[10px] text-forest hover:underline"
												>
													{finding.affected_url}
												</button>
											</div>
											<p className="text-xs leading-relaxed text-[#53615b]">
												{finding.explanation}
											</p>
											<p className="mt-2 text-[11px] font-medium text-ink">
												Action: {finding.recommended_action}
											</p>
										</article>
									))}
								</div>
							) : (
								<EmptyState
									title={
										audit?.status === "COMPLETED"
											? "No findings for this filter"
											: "No audit results"
									}
									text={
										audit?.status === "COMPLETED"
											? "Try another severity filter or run a fresh audit."
											: "Run an audit after crawling pages to see evidence-backed technical checks."
									}
								/>
							)}
						</div>
						<div className="rounded-2xl border border-line bg-white p-5 shadow-soft md:p-6">
							<div className="mb-4 flex items-center justify-between">
								<div>
									<h2 className="text-base font-semibold">Indexed pages</h2>
									<p className="mt-1 text-xs text-muted">
										Page records persisted for this project.
									</p>
								</div>
								<span className="text-xs font-semibold text-muted">
									{pages.length} pages
								</span>
							</div>
							{pages.length ? (
								<div className="max-h-[390px] divide-y divide-line overflow-auto">
									{pages.slice(0, 30).map((page) => (
										<button type="button"
											onClick={() => setSelectedPage(page)}
											key={page.id}
											className="flex w-full items-start gap-3 py-3 text-left hover:bg-canvas/80"
										>
											<div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-canvas text-muted">
												<FileSearch size={15} />
											</div>
											<div className="min-w-0 flex-1">
												<div className="truncate text-xs font-semibold">
													{page.title || "Untitled page"}
												</div>
												<div className="mt-1 truncate text-[10px] text-muted">
													{page.url}
												</div>
											</div>
											<span className="whitespace-nowrap text-[10px] text-muted">
												{page.word_count} words
											</span>
										</button>
									))}
								</div>
							) : (
								<EmptyState
									title="Pages appear after a crawl"
									text="The explorer reads persisted pages from the selected project."
								/>
							)}
						</div>
					</section>

					<section className="mb-8 grid gap-5 xl:grid-cols-[1fr_1fr]">
						<div className="rounded-2xl border border-line bg-white p-5 shadow-soft md:p-6">
							<div className="mb-4 flex items-center justify-between">
								<div>
									<h2 className="text-base font-semibold">
										Search indexed content
									</h2>
									<p className="mt-1 text-xs text-muted">
										Hybrid lexical and vector results from this project.
									</p>
								</div>
								<Search size={17} className="text-muted" />
							</div>
							<form onSubmit={runSearch} className="flex gap-2">
								<input
									value={searchText}
									onChange={(event) => setSearchText(event.target.value)}
									placeholder="Find a topic or phrase…"
									className="h-10 min-w-0 flex-1 rounded-lg border border-line px-3 text-sm outline-none focus:border-forest"
								/>
								<button type="submit"
									disabled={!projectId || !!busy}
									className="grid h-10 w-10 place-items-center rounded-lg bg-forest text-white"
								>
									<Search size={16} />
								</button>
							</form>
							{query && (
								<div className="mt-4">
									<div className="mb-2 text-[11px] font-semibold text-muted">
										Results for “{query}”
									</div>
									{searchResults.length ? (
										<div className="space-y-2">
											{searchResults.map((item) => (
												<div
													key={`${item.url}-${item.score}`}
													className="rounded-lg border border-line p-3"
												>
													<div className="truncate text-xs font-semibold">
														{item.title || item.url}
													</div>
													<p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-muted">
														{item.snippet}
													</p>
													<a
														href={item.url}
														target="_blank"
														rel="noreferrer"
														className="mt-1 block truncate text-[10px] text-forest"
													>
														{item.url}
													</a>
												</div>
											))}
										</div>
									) : (
										<p className="rounded-lg bg-canvas p-3 text-xs text-muted">
											No indexed evidence matched this query.
										</p>
									)}
								</div>
							)}
						</div>
						<div
							id="assistant"
							className="rounded-2xl border border-[#cddfd4] bg-[#fafffc] p-5 shadow-soft md:p-6"
						>
							<div className="mb-4 flex items-center gap-3">
								<div className="grid h-9 w-9 place-items-center rounded-xl bg-forest text-white">
									<Bot size={18} />
								</div>
								<div>
									<h2 className="text-base font-semibold">Ask your website</h2>
									<p className="mt-1 text-xs text-muted">
										Answers are grounded in retrieved pages and include
										citations.
									</p>
								</div>
							</div>
							<form onSubmit={askAssistant} className="flex gap-2">
								<input
									value={question}
									onChange={(event) => setQuestion(event.target.value)}
									placeholder="What does my site say about…"
									className="h-10 min-w-0 flex-1 rounded-lg border border-line bg-white px-3 text-sm outline-none focus:border-forest"
								/>
								<button type="submit"
									disabled={!projectId || !!busy}
									className="grid h-10 w-10 place-items-center rounded-lg bg-forest text-white"
								>
									<Send size={15} />
								</button>
							</form>
							{rag && (
								<div className="mt-4 rounded-xl border border-line bg-white p-4">
									<div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-forest">
										<Sparkles size={13} />
										{rag.grounded
											? "Evidence-grounded answer"
											: "Insufficient evidence"}
									</div>
									<p className="whitespace-pre-wrap text-xs leading-relaxed text-[#34433d]">
										{rag.answer}
									</p>
									{rag.citations.length > 0 && (
										<div className="mt-4 border-t border-line pt-3">
											<div className="mb-2 text-[10px] font-semibold text-muted">
												SOURCES
											</div>
											<div className="space-y-2">
												{rag.citations.map((citation) => (
													<a
														key={citation.citation_number}
														href={citation.url}
														target="_blank"
														rel="noreferrer"
														className="block rounded-lg bg-canvas p-2.5"
													>
														<div className="truncate text-[10px] font-semibold text-forest">
															[{citation.citation_number}]{" "}
															{citation.page_title || citation.url}
														</div>
														<div className="mt-1 line-clamp-2 text-[10px] text-muted">
															{citation.supporting_snippet}
														</div>
													</a>
												))}
											</div>
										</div>
									)}
								</div>
							)}
							{!rag && (
								<div className="mt-4 flex items-start gap-2 rounded-lg bg-[#f1f7f3] p-3 text-[10px] leading-relaxed text-muted">
									<CircleHelp
										size={14}
										className="mt-0.5 shrink-0 text-forest"
									/>
									The assistant only has access to pages indexed for this
									project. If sources are missing, crawl the site first.
								</div>
							)}
						</div>
					</section>
					<footer className="flex flex-col justify-between gap-2 border-t border-line py-5 text-[10px] text-muted sm:flex-row">
						<span>SearchIntel AI · Local development workspace</span>
						<span>
							SEO signals are diagnostic guidance, not search-engine ranking
							guarantees.
						</span>
					</footer>
				</div>
			</main>

			{showProjectForm && (
				<Modal
					title="Create a project"
					onClose={() => setShowProjectForm(false)}
				>
					<form onSubmit={createProject} className="space-y-4">
						<Field id="project-name" label="Project name">
							<input
								id="project-name"
								required
								value={projectName}
								onChange={(event) => setProjectName(event.target.value)}
								placeholder="Acme website"
								className="form-control"
							/>
						</Field>
						<Field id="project-website" label="Primary website (optional)">
							<input
								id="project-website"
								type="url"
								value={projectUrl}
								onChange={(event) => setProjectUrl(event.target.value)}
								placeholder="https://example.com"
								className="form-control"
							/>
						</Field>
						<div className="flex justify-end gap-2 pt-2">
							<button
								type="button"
								onClick={() => setShowProjectForm(false)}
								className="btn-secondary"
							>
								Cancel
							</button>
							<button type="submit" disabled={busy === "project"} className="btn-primary">
								{busy === "project" ? "Creating…" : "Create project"}
							</button>
						</div>
					</form>
				</Modal>
			)}
			{showWebsiteForm && (
				<Modal
					title="Register a website"
					onClose={() => setShowWebsiteForm(false)}
				>
					<form onSubmit={addWebsite} className="space-y-4">
						<Field id="website-url" label="Website URL">
							<input
								id="website-url"
								required
								type="url"
								value={newWebsiteUrl}
								onChange={(event) => setNewWebsiteUrl(event.target.value)}
								placeholder="https://example.com"
								className="form-control"
							/>
						</Field>
						<p className="text-[11px] leading-relaxed text-muted">
							Crawls stay on this hostname, respect robots.txt, and use your
							configured page and rate limits.
						</p>
						<div className="flex justify-end gap-2 pt-2">
							<button
								type="button"
								onClick={() => setShowWebsiteForm(false)}
								className="btn-secondary"
							>
								Cancel
							</button>
							<button type="submit" disabled={busy === "website"} className="btn-primary">
								{busy === "website" ? "Saving…" : "Register website"}
							</button>
						</div>
					</form>
				</Modal>
			)}
			{selectedPage && (
				<Modal
					title={selectedPage.title || "Page details"}
					onClose={() => setSelectedPage(null)}
					wide
				>
					<div className="mb-4 break-all text-xs text-forest">
						{selectedPage.url}
					</div>
					<div className="mb-4 grid grid-cols-2 gap-2 text-[11px]">
						<div className="rounded-lg bg-canvas p-3">
							<div className="text-muted">Words</div>
							<div className="mt-1 font-semibold">
								{selectedPage.word_count}
							</div>
						</div>
						<div className="rounded-lg bg-canvas p-3">
							<div className="text-muted">Last crawled</div>
							<div className="mt-1 font-semibold">
								{shortDate(selectedPage.crawled_at)}
							</div>
						</div>
					</div>
					<button type="button"
						onClick={() =>
							window.open(
								`${API}/pages/${selectedPage.id}?tenant_id=${encodeURIComponent(tenant)}`,
								"_blank",
								"noopener,noreferrer",
							)
						}
						className="btn-secondary"
					>
						Open page API record
					</button>
					<p className="mt-3 text-[10px] text-muted">
						The page detail endpoint is served by the backend; this explorer
						does not invent missing metadata.
					</p>
				</Modal>
			)}
		</div>
	);
}

function MetricCard({
	label,
	value,
	helper,
	icon,
	trend,
}: {
	label: string;
	value: string;
	helper: string;
	icon: React.ReactNode;
	trend: string;
}) {
	return (
		<div className="rounded-2xl border border-line bg-white p-4 shadow-soft">
			<div className="mb-4 flex items-center justify-between">
				<div className="text-[11px] font-medium text-muted">{label}</div>
				<div className="grid h-8 w-8 place-items-center rounded-lg bg-canvas text-forest">
					{icon}
				</div>
			</div>
			<div className="truncate text-[23px] font-semibold tracking-tight">
				{value}
			</div>
			<div className="mt-1 truncate text-[10px] text-muted">{helper}</div>
			<div className="mt-3 flex items-center gap-1 text-[10px] font-medium text-forest">
				<ArrowUpRight size={12} />
				{trend}
			</div>
		</div>
	);
}
function Severity({ severity }: { severity: string }) {
	const style =
		severity === "error"
			? "bg-red-50 text-red-700"
			: severity === "warning"
				? "bg-amber-50 text-amber-700"
				: "bg-slate-100 text-slate-600";
	return (
		<span
			className={`rounded-full px-2 py-1 text-[9px] font-semibold uppercase ${style}`}
		>
			{severity}
		</span>
	);
}
function EmptyState({
	title,
	text,
	action,
	onClick,
}: {
	title: string;
	text: string;
	action?: string;
	onClick?: () => void;
}) {
	return (
		<div className="grid min-h-[150px] place-items-center rounded-xl border border-dashed border-line px-5 py-7 text-center">
			<div>
				<div className="mx-auto mb-2 grid h-9 w-9 place-items-center rounded-full bg-canvas text-muted">
					<Clock3 size={16} />
				</div>
				<div className="text-xs font-semibold">{title}</div>
				<p className="mx-auto mt-1 max-w-[260px] text-[10px] leading-relaxed text-muted">
					{text}
				</p>
				{action && onClick && (
					<button type="button"
						onClick={onClick}
						className="mt-3 text-[10px] font-semibold text-forest hover:underline"
					>
						{action}
					</button>
				)}
			</div>
		</div>
	);
}
function Field({
	id,
	label,
	children,
}: {
	id: string;
	label: string;
	children: React.ReactNode;
}) {
	return (
		<div className="block">
			<label htmlFor={id} className="text-xs font-semibold text-ink">
				{label}
			</label>
			<div className="mt-1.5">{children}</div>
		</div>
	);
}
function Modal({
	title,
	onClose,
	children,
	wide,
}: {
	title: string;
	onClose: () => void;
	children: React.ReactNode;
	wide?: boolean;
}) {
	return (
		<div
			className="fixed inset-0 z-40 grid place-items-center bg-[#10251d]/45 p-4"
		>
			<section
				role="dialog"
				aria-modal="true"
				aria-label={title}
				className={`w-full rounded-2xl bg-white p-5 shadow-2xl ${wide ? "max-w-xl" : "max-w-md"}`}
			>
				<div className="mb-5 flex items-center justify-between">
					<h3 className="text-base font-semibold">{title}</h3>
					<button type="button"
						aria-label="Close dialog"
						onClick={onClose}
						className="grid h-8 w-8 place-items-center rounded-lg hover:bg-canvas"
					>
						<X size={16} />
					</button>
				</div>
				{children}
			</section>
		</div>
	);
}
