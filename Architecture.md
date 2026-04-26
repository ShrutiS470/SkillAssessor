```mermaid
%% Entry point
U[User] -->|Paste resume & JD / start| Root[ResumeJDAssessmentApp<br/>(SequentialAgent)]

%% Root pipeline
subgraph RootPipeline[Root SequentialAgent]
    direction TB

    %% Callback
    Init[initialize_state<br/>(before_agent_callback)]

    %% Intake
    Intake[IntakeAgent<br/>(LlmAgent)]
    SaveTool[[save_pasted_resume_jd<br/>(tool)]]

    %% Assessment pipeline
    subgraph Assessment[AssessmentPipeline<br/>(SequentialAgent)]
        direction TB

        SE[SkillExtractorAgent<br/>(LlmAgent)]
        PP[PriorityProjectionAgent<br/>(LlmAgent)]

        %% Interview loop
        subgraph Loop[InterviewLoop<br/>(LoopAgent, max 5)]
            direction TB
            AS[AssessorAgent<br/>(LlmAgent)]
            CA[CandidateAgent<br/>(LlmAgent)]
            EV[EvaluatorAgent<br/>(LlmAgent)]
            MG[MergeAgent<br/>(LlmAgent)]
            MergeTool[[merge_evaluation_bundle<br/>(tool)]]
            SD[StopDeciderAgent<br/>(LlmAgent)]
            LX[LoopExitAgent<br/>(LlmAgent)]
            ExitTool[[exit_loop<br/>(tool)]]
        end

        GA[GapAnalysisAgent<br/>(LlmAgent)]
        LP[LearningPlanAgent<br/>(LlmAgent)]
        FR[FinalReportAgent<br/>(LlmAgent)]
    end
end

%% Wiring inside root
Root --> Init
Init --> Intake

%% Intake logic
Intake -->|needs resume+JD| U
Intake -->|has RESUME & JD| SaveTool
SaveTool --> Intake
Intake -->|READY_FOR_ASSESSMENT| Assessment

%% Assessment sequence
Assessment --> SE --> PP --> Loop --> GA --> LP --> FR
FR -->|final_report (Markdown)| U

%% Interview loop internals
AS --> CA --> EV --> MG
MG --> MergeTool --> MG
MG --> SD
SD -->|CONTINUE| AS
SD -->|ASSESSMENT_COMPLETE| LX
LX --> ExitTool -->|escalate / end loop| GA
```
