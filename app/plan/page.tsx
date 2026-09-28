"use client";

import { DashboardShell } from "@/components/Dashboard";
import { PlanPricing } from "@/components/PlanPricing";

/**
 * Plan and billing.
 *
 * Only that. This page also used to carry a four-week practice schedule, which
 * collided two different meanings of "plan" and buried the pricing under
 * advice derived from nobody's scorecards. Practice guidance belongs where it
 * can be specific: the report already produces it from the evaluators' own
 * flags, quoting the aspirant back to themselves.
 */

export default function PlanPage() {
  return (
    <DashboardShell
      title="My plan"
      lede="What you are on today, what it will cost when preview ends, and what a single interview costs to run."
    >
      <PlanPricing />
    </DashboardShell>
  );
}
