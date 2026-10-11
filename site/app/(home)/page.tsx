import Image from 'next/image';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { ArrowRight, ArrowUpRight, Bell, Bot, CalendarDays, Code, Cpu, FileSearch, Gamepad2, KeyRound, Lock, Newspaper, Plug, Rocket, ScrollText, ShieldCheck, ShoppingBag, Timer, Users } from 'lucide-react';
import { DemoVideo } from '@/components/demo-video';
import { Contributors } from '@/components/contributors';
import { BuiltBy, OrgMarks } from '@/components/org-marks';
import { repoUrl } from '@/lib/shared';

type Module = { icon: typeof Cpu; name: string; text: string; href?: string };

const modules: Module[] = [
  {
    icon: Users,
    name: 'Members and points',
    text: 'A member list, points from events and a leaderboard.',
    href: '/docs/modules/points',
  },
  {
    icon: ShoppingBag,
    name: 'Merch store',
    text: 'Members spend points. Officers manage products and orders.',
    href: '/docs/modules/storefront',
  },
  {
    icon: CalendarDays,
    name: 'Calendar sync',
    text: 'Notion events go to Google Calendar and a public feed.',
    href: '/docs/modules/calendar',
  },
  { icon: Bell, name: 'Alerts', text: 'Org events, such as a failed job or a site that is down, in your Discord channels.', href: '/docs/codebase/webhooks' },
  { icon: Newspaper, name: 'Feeds', text: 'Job and hackathon posts in your Discord channels.', href: '/docs/modules/feeds' },
  {
    icon: Gamepad2,
    name: 'Discord bot',
    text: 'One bot for every org, with slash commands and games.',
    href: '/docs/modules/discord-bot',
  },
  {
    icon: Code,
    name: 'LeetCode',
    text: 'The daily question in Discord, with solve checks.',
    href: '/docs/modules/leetcode',
  },
  {
    icon: FileSearch,
    name: 'Knowledge search',
    text: 'Search over org documents and public pages.',
    href: '/docs/modules/knowledge',
  },
  { icon: Bot, name: 'Agent memory', text: 'Conversations and memories for each member.', href: '/docs/modules/agents' },
  {
    icon: KeyRound,
    name: 'Member accounts',
    text: 'Canvas, Google Calendar and Outlook, for agents to use.',
    href: '/docs/modules/accounts',
  },
  { icon: Cpu, name: 'Godfather pods', text: 'GPU and CPU pods that members reach over SSH.', href: '/docs/modules/godfather' },
  {
    icon: Rocket,
    name: 'Hosting',
    text: 'Deploy org apps with health checks and rollback.',
    href: '/docs/modules/runpod-apps',
  },
  {
    icon: Plug,
    name: 'MCP tools',
    text: 'The tools of each feature for agents, with scoped tokens.',
    href: '/docs/codebase/architecture#tools-and-the-mcp-server',
  },
];

const shots = [
  { name: 'explore', title: 'Features', alt: 'Explore page with the features an org can add' },
  { name: 'tokens', title: 'Scoped tokens', alt: 'Tokens page with a new agent token and its scopes' },
  { name: 'godfather', title: 'Godfather pods', alt: 'Godfather page with the org pods and their sessions' },
];

const access = [
  { icon: ShieldCheck, name: 'Access checks', text: 'Member and officer checks on every org route.' },
  { icon: ScrollText, name: 'Audit log', text: 'Each change by an officer or a token is recorded.' },
  { icon: Lock, name: 'Encrypted secrets', text: 'Org secrets and OAuth grants are encrypted at rest.' },
  { icon: Timer, name: 'Short-lived access', text: 'SSH certificates last 12 hours. Tokens are revocable.' },
];

const primaryButton =
  'inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-fd-foreground px-5 text-sm font-medium text-fd-background transition-[opacity,transform] duration-150 ease-out hover:opacity-85 active:scale-[0.98]';
const secondaryButton =
  'inline-flex h-10 items-center justify-center gap-2 rounded-lg border bg-fd-background px-5 text-sm font-medium transition-[background-color,transform] duration-150 ease-out hover:bg-fd-accent active:scale-[0.98]';

export default function HomePage() {
  return (
    <main className="flex flex-1 flex-col">
      <Hero />
      <Section eyebrow="Features" title="Turn on what your org uses." text="Each org is a Discord server with its own features.">
        <div className="grid gap-px overflow-hidden rounded-xl border bg-fd-border grid-cols-2 lg:grid-cols-4">
          {modules.map((m) => (
            <Feature key={m.name} {...m} />
          ))}
        </div>
      </Section>
      <Section eyebrow="Dashboard" title="One dashboard for each org." text="Officers manage features, tokens and pods.">
        <div className="grid gap-6 md:grid-cols-3">
          {shots.map((s) => (
            <figure key={s.name}>
              <Screenshot name={s.name} alt={s.alt} sizes="(min-width: 768px) 320px, 100vw" />
              <figcaption className="mt-3 text-sm font-medium">{s.title}</figcaption>
            </figure>
          ))}
        </div>
      </Section>
      <Section eyebrow="Access" title="Member data stays in its org.">
        <div className="grid grid-cols-2 gap-x-6 gap-y-8 md:gap-x-10 lg:grid-cols-4">
          {access.map((a) => (
            <div key={a.name}>
              <a.icon className="size-5 text-fd-muted-foreground" />
              <h3 className="mt-4 text-sm font-medium">{a.name}</h3>
              <p className="mt-1 text-sm text-fd-muted-foreground">{a.text}</p>
            </div>
          ))}
        </div>
      </Section>
      <CallToAction />
      <Footer />
    </main>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden border-b">
      <div className="grid-bg pointer-events-none absolute inset-0" />
      <div className="relative mx-auto flex max-w-5xl flex-col items-center px-6 pt-20 pb-16 text-center md:pt-28">
        <a
          href={repoUrl}
          className="mb-8 inline-flex items-center gap-2 rounded-full border bg-fd-background px-3 py-1 text-xs text-fd-muted-foreground transition-colors duration-150 ease-out hover:text-fd-foreground"
        >
          Open source
          <span className="h-3 w-px bg-fd-border" />
          Self-hosted
        </a>
        <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-balance md:text-6xl">
          Infrastructure for student organizations
        </h1>
        <p className="mt-5 max-w-xl text-base text-pretty text-fd-muted-foreground md:text-lg">
          One deployment for many orgs, each with the features it needs.
        </p>
        <div className="mt-8 flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
          <Link href="/docs" className={primaryButton}>
            Read the docs
            <ArrowRight className="size-4" />
          </Link>
          <a href={repoUrl} className={secondaryButton}>
            View on GitHub
          </a>
        </div>
        <div className="mt-10 flex items-center gap-3 text-sm text-fd-muted-foreground">
          <OrgMarks />
          <BuiltBy />
        </div>
        <Contributors className="mt-6 flex flex-col items-center" />
        <DemoVideo className="mt-14 w-full" />
      </div>
    </section>
  );
}

function Section({
  eyebrow,
  title,
  text,
  children,
}: {
  eyebrow: string;
  title: string;
  text?: string;
  children: ReactNode;
}) {
  return (
    <section className="border-b">
      <div className="mx-auto max-w-5xl px-6 py-20 md:py-24">
        <p className="font-mono text-xs tracking-wider text-fd-muted-foreground uppercase">{eyebrow}</p>
        <h2 className="mt-3 max-w-2xl text-2xl font-semibold tracking-tight text-balance md:text-4xl">{title}</h2>
        {text ? <p className="mt-3 max-w-2xl text-fd-muted-foreground text-pretty">{text}</p> : null}
        <div className="mt-10">{children}</div>
      </div>
    </section>
  );
}

function Feature({ icon: Icon, name, text, href }: Module) {
  const body = (
    <>
      <div className="flex items-center justify-between">
        <Icon className="size-5" />
        {href ? (
          <ArrowUpRight className="size-4 text-fd-muted-foreground opacity-0 transition-opacity duration-150 ease-out group-hover:opacity-100" />
        ) : null}
      </div>
      <h3 className="mt-4 text-sm font-medium">{name}</h3>
      <p className="mt-1 text-sm text-fd-muted-foreground">{text}</p>
    </>
  );
  if (!href) return <div className="bg-fd-background p-4 sm:p-5">{body}</div>;
  return (
    <Link
      href={href}
      className="group bg-fd-background p-4 sm:p-5 transition-colors duration-150 ease-out outline-none hover:bg-fd-accent/50 focus-visible:bg-fd-accent/50"
    >
      {body}
    </Link>
  );
}

function Screenshot({
  name,
  alt,
  sizes,
  preload = false,
  className = '',
}: {
  name: string;
  alt: string;
  sizes: string;
  preload?: boolean;
  className?: string;
}) {
  const props = { alt, width: 2880, height: 1800, sizes, preload, loading: preload ? undefined : ('lazy' as const) };
  return (
    <div className={`rounded-xl border bg-fd-card p-1.5 shadow-sm ${className}`}>
      <div className="overflow-hidden rounded-lg border">
        <Image src={`/screenshots/${name}-light.webp`} className="block h-auto w-full dark:hidden" {...props} />
        <Image src={`/screenshots/${name}-dark.webp`} className="hidden h-auto w-full dark:block" {...props} />
      </div>
    </div>
  );
}

function CallToAction() {
  return (
    <section className="border-b">
      <div className="mx-auto flex max-w-5xl flex-col items-start gap-6 px-6 py-16 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">Run it for your org.</h2>
          <p className="mt-2 text-fd-muted-foreground">Postgres or SQLite, with Docker or on one RunPod pod.</p>
        </div>
        <div className="flex gap-3">
          <Link href="/docs/quickstart" className={primaryButton}>
            Quickstart
          </Link>
          <a href={repoUrl} className={secondaryButton}>
            GitHub
          </a>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  const link = 'transition-colors duration-150 ease-out hover:text-fd-foreground';
  return (
    <footer className="mx-auto flex w-full max-w-5xl flex-col gap-4 px-6 py-10 text-xs text-fd-muted-foreground sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <OrgMarks size="sm" />
        <BuiltBy />
      </div>
      <nav aria-label="Footer" className="flex gap-4">
        <Link href="/docs" className={link}>
          Docs
        </Link>
        <a href={repoUrl} className={link}>
          GitHub
        </a>
        <a href={`${repoUrl}/blob/main/LICENSE`} className={link}>
          License
        </a>
      </nav>
    </footer>
  );
}
