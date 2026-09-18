"use client";

import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { AgentMode } from "@/types/conversation";

type QuickstartPreCallCardProps = {
	isLoading: boolean;
	error: string | null;
	agentMode: AgentMode;
	onAgentModeChange: (mode: AgentMode) => void;
	onStartConversation: () => void;
};

export function QuickstartPreCallCard({
	isLoading,
	error,
	agentMode,
	onAgentModeChange,
	onStartConversation,
}: QuickstartPreCallCardProps) {
	return (
		<div
			className="mx-auto flex w-[min(92vw,26.25rem)] animate-fade-up flex-col items-center rounded-[20px] border border-[#2b2b2b] px-10 py-10 text-center shadow-[0_10px_24px_rgba(0,0,0,0.28)]"
			style={{
				backgroundImage:
					"linear-gradient(164.988deg, rgba(54,54,54,0.2) 1.0596%, rgba(0,0,0,0) 96.089%), linear-gradient(90deg, rgb(16,16,16) 0%, rgb(16,16,16) 100%)",
			}}
		>
			<h1 className="text-[28px] font-medium leading-[1.2] text-white">
				Custom HTTP Tools Recipe
			</h1>
			<p className="mt-[14px] text-sm font-medium leading-6 text-muted-foreground">
				Ask the agent to create or look up a support ticket &mdash; the model
				selects a tool and Agora Engine calls your HTTP endpoint.
			</p>

			<fieldset disabled={isLoading} className="mt-8 w-full text-left">
				<legend className="mb-3 text-sm font-medium text-white">
					Agent mode
				</legend>
				<div className="grid grid-cols-2 gap-2">
					{(["pipeline", "realtime"] as const).map((mode) => (
						<label key={mode} className="cursor-pointer">
							<input
								type="radio"
								name="agentMode"
								value={mode}
								checked={agentMode === mode}
								onChange={() => onAgentModeChange(mode)}
								className="peer sr-only"
							/>
							<span className="flex h-10 items-center justify-center rounded-lg border border-[#2b2b2b] text-sm text-muted-foreground transition-colors peer-checked:border-primary peer-checked:bg-primary/10 peer-checked:text-primary peer-focus-visible:ring-2 peer-focus-visible:ring-primary peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-background peer-disabled:cursor-not-allowed peer-disabled:opacity-50">
								{mode === "pipeline" ? "Pipeline" : "Realtime"}
							</span>
						</label>
					))}
				</div>
			</fieldset>

			<Button
				onClick={onStartConversation}
				disabled={isLoading}
				className="mt-6 h-10 w-full rounded-lg border border-primary bg-primary text-sm font-medium text-black hover:border-white hover:bg-white hover:text-black disabled:hover:border-primary disabled:hover:bg-primary disabled:hover:text-black"
				aria-label={
					isLoading
						? "Starting conversation with AI agent"
						: "Start conversation with AI agent"
				}
			>
				{isLoading ? (
					<>
						<Loader2 className="h-4 w-4 animate-spin" />
						Starting...
					</>
				) : (
					"Start Conversation"
				)}
			</Button>
			{error ? <p className="mt-3 text-xs text-destructive">{error}</p> : null}
		</div>
	);
}
