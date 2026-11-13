import { SegmentedControl } from "../../components/Controls";
import type { AnalyticsTab } from "../../utils/analyticsQuery";

const TAB_OPTIONS: { id: AnalyticsTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "predictive", label: "Predictive Intelligence" },
  { id: "decisions", label: "Decision Insights" },
  { id: "quality", label: "Data Quality" },
];

export function AnalyticsWorkspaceTabs({
  value,
  onChange,
}: {
  value: AnalyticsTab;
  onChange: (tab: AnalyticsTab) => void;
}) {
  return (
    <div className="analytics-workspace-tabs">
      <SegmentedControl<AnalyticsTab>
        label="Analytics workspace"
        value={value}
        onChange={onChange}
        options={TAB_OPTIONS}
      />
    </div>
  );
}
