"use client";

import type { AgentMode } from "@/types/conversation";

export type QuickstartAgentMetric = {
	type: string;
	name: string;
	value: number;
	timestamp: number;
};

type QuickstartPipelineMetricsProps = {
	metrics: QuickstartAgentMetric[];
	agentMode: AgentMode;
};

const PIPELINES = {
	pipeline: [
		{ key: "stt", label: "Deepgram STT", metricTypes: ["stt", "asr"] },
		{ key: "llm", label: "OpenAI LLM", metricTypes: ["llm"] },
		{ key: "tts", label: "MiniMax TTS", metricTypes: ["tts"] },
	],
	realtime: [
		{
			key: "mllm",
			label: "OpenAI Realtime MLLM",
			metricTypes: ["mllm", "llm"],
		},
	],
} as const;

function formatMetricName(name: string) {
	return name.replace(/[_-]+/g, " ");
}

export function QuickstartPipelineMetrics({
	metrics,
	agentMode,
}: QuickstartPipelineMetricsProps) {
	const pipeline = PIPELINES[agentMode];
	const latestByType = new Map<string, QuickstartAgentMetric>();
	for (const metric of metrics) {
		latestByType.set(metric.type.toLowerCase(), metric);
	}

	return (
		<div className="flex min-w-0 flex-wrap items-center gap-2">
			<span className="text-sm font-medium leading-6 text-muted-foreground">
				Pipeline
			</span>
			{pipeline.map((step, index) => {
				const metric = step.metricTypes
					.map((type) => latestByType.get(type))
					.find(Boolean);

				return (
					<div key={step.key} className="flex items-center gap-2">
						{index > 0 ? (
							<span
								className="text-xs text-muted-foreground"
								aria-hidden="true"
							>
								/
							</span>
						) : null}
						<span className="rounded-md border border-border bg-transparent px-2 py-0.5 text-xs font-semibold leading-4 text-foreground shadow-sm">
							{step.label}
							{metric ? (
								<span
									className="ml-2 text-primary"
									title={new Date(metric.timestamp).toLocaleTimeString()}
								>
									{formatMetricName(metric.name)} {Math.round(metric.value)}ms
								</span>
							) : null}
						</span>
					</div>
				);
			})}
		</div>
	);
}
