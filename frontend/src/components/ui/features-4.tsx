import { Badge } from "./badge";
import { Card } from "./card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./tabs";
import { cn } from "../../lib/utils";
import { IconPlaceholder } from "./features-4-utils/icon-placeholder";

/** Props a call site may pass through to an icon. */
type IconProps = { className?: string; size?: number | string };

type Feature = {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
};

type FeatureTab = {
  value: string;
  label: string;
  features: Feature[];
};

const TABS: FeatureTab[] = [
  {
    value: "collaboration",
    label: "Collaboration",
    features: [
      {
        icon: (p: IconProps) => (
          <IconPlaceholder
            lucide="Group"
            tabler="IconUsers"
            hugeicons="GroupIcon"
            phosphor="Users"
            remixicon="RiGroupLine"
            {...p}
          />
        ),
        title: "Shared workspaces",
        description:
          "Bring every team into one workspace with granular roles and instant invites.",
      },
      {
        icon: (p: IconProps) => (
          <IconPlaceholder
            lucide="MessageCircle"
            tabler="IconMessageCircle"
            hugeicons="Message01Icon"
            phosphor="ChatCircle"
            remixicon="RiChat3Line"
            {...p}
          />
        ),
        title: "Inline comments",
        description:
          "Discuss changes in context with threaded comments, mentions, and reactions.",
      },
      {
        icon: (p: IconProps) => (
          <IconPlaceholder
            lucide="History"
            tabler="IconHistory"
            hugeicons="HistoryIcon"
            phosphor="ClockCounterClockwise"
            remixicon="RiHistoryLine"
            {...p}
          />
        ),
        title: "Version history",
        description:
          "Track every edit and restore any previous state with a single click.",
      },
    ],
  },
  {
    value: "automation",
    label: "Automation",
    features: [
      {
        icon: (p: IconProps) => (
          <IconPlaceholder
            lucide="Flashlight"
            tabler="IconBulb"
            hugeicons="FlashlightIcon"
            phosphor="Flashlight"
            remixicon="RiFlashlightLine"
            {...p}
          />
        ),
        title: "Visual workflows",
        description:
          "Chain triggers and actions on a drag-and-drop canvas, no code required.",
      },
      {
        icon: (p: IconProps) => (
          <IconPlaceholder
            lucide="Bot"
            tabler="IconRobot"
            hugeicons="RobotIcon"
            phosphor="Robot"
            remixicon="RiRobot2Line"
            {...p}
          />
        ),
        title: "Smart agents",
        description:
          "Let Acme agents triage requests, draft replies, and route work for you.",
      },
      {
        icon: (p: IconProps) => (
          <IconPlaceholder
            lucide="Timer"
            tabler="IconClockBolt"
            hugeicons="TimerIcon"
            phosphor="Timer"
            remixicon="RiTimerFlashLine"
            {...p}
          />
        ),
        title: "Scheduled runs",
        description:
          "Queue recurring jobs down to the minute with built-in retries and alerts.",
      },
    ],
  },
  {
    value: "security",
    label: "Security",
    features: [
      {
        icon: (p: IconProps) => (
          <IconPlaceholder
            lucide="ShieldCheck"
            tabler="IconShieldCheck"
            hugeicons="Shield01Icon"
            phosphor="ShieldCheck"
            remixicon="RiShieldCheckLine"
            {...p}
          />
        ),
        title: "SOC 2 Type II",
        description:
          "Independently audited controls keep your data compliant and protected.",
      },
      {
        icon: (p: IconProps) => (
          <IconPlaceholder
            lucide="Key"
            tabler="IconKey"
            hugeicons="KeyIcon"
            phosphor="Key"
            remixicon="RiKeyLine"
            {...p}
          />
        ),
        title: "SSO & SCIM",
        description:
          "Provision users through SAML, OIDC, and automated directory sync.",
      },
      {
        icon: (p: IconProps) => (
          <IconPlaceholder
            lucide="Fingerprint"
            tabler="IconFingerprint"
            hugeicons="FingerPrintIcon"
            phosphor="Fingerprint"
            remixicon="RiFingerprintLine"
            {...p}
          />
        ),
        title: "Audit logging",
        description:
          "Every action is timestamped, immutable, and exportable to your SIEM.",
      },
    ],
  },
];

export default function FeaturesBlock() {
  return (
    <section className="flex w-full items-center justify-center bg-background px-6 py-16 text-foreground">
      <div className="mx-auto w-full max-w-5xl">
        <div className="flex flex-col items-center text-center">
          <Badge variant="secondary" className="gap-1.5">
            <IconPlaceholder
              lucide="Braces"
              tabler="IconBraces"
              hugeicons="BracesIcon"
              phosphor="BracketsCurly"
              remixicon="RiBracesLine"
              data-icon="inline-start"
              className="size-3.5"
            />
            Built for teams
          </Badge>
          <h2 className="mt-4 font-heading text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            Everything you need to ship faster
          </h2>
          <p className="mt-3 max-w-xl text-pretty text-muted-foreground">
            Acme brings collaboration, automation, and enterprise-grade security
            together in one connected platform.
          </p>
        </div>

        <Tabs
          defaultValue="collaboration"
          className="mt-10 w-full items-center"
        >
          <TabsList className="h-auto flex-wrap gap-1 rounded-lg p-1">
            {TABS.map((tab) => (
              <TabsTrigger
                key={tab.value}
                value={tab.value}
                className="rounded-md px-4 py-1.5 text-sm"
              >
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>

          {TABS.map((tab) => (
            <TabsContent key={tab.value} value={tab.value} className="mt-8">
              <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
                {tab.features.map((feature) => {
                  const Icon = feature.icon;
                  return (
                    <Card
                      key={feature.title}
                      className="group h-full gap-4 p-6 transition-colors hover:border-primary/40"
                    >
                      <div
                        className={cn(
                          "flex size-11 items-center justify-center rounded-md",
                          "bg-primary/10 text-primary transition-colors",
                          "group-hover:bg-primary group-hover:text-primary-foreground",
                        )}
                      >
                        <Icon className="size-5" />
                      </div>
                      <div className="space-y-1.5">
                        <h3 className="font-heading text-base font-medium">
                          {feature.title}
                        </h3>
                        <p className="text-sm/relaxed text-muted-foreground">
                          {feature.description}
                        </p>
                      </div>
                      <div className="mt-auto flex items-center gap-2 text-xs font-medium text-muted-foreground">
                        <IconPlaceholder
                          lucide="GitBranch"
                          tabler="IconGitBranch"
                          hugeicons="GitBranchIcon"
                          phosphor="GitBranch"
                          remixicon="RiGitBranchLine"
                          className="size-3.5"
                        />
                        Included on every plan
                      </div>
                    </Card>
                  );
                })}
              </div>
            </TabsContent>
          ))}
        </Tabs>
      </div>
    </section>
  );
}
