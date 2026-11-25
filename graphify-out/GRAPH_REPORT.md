# Graph Report - zuno  (2026-11-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 2096 nodes · 4911 edges · 116 communities (94 shown, 22 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 322 edges (avg confidence: 0.91)
- Token cost: 8,576 input · 1,144 output

## Graph Freshness
- Built from commit: `f57a3d8e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Human Inbox Management
- Mobile App Dependencies
- Agora Join Payload Builder
- Background Tasks Config
- RTC Token and Call API
- Espo Calendar Store
- Voice Direction Layer
- Handoff and Admin Service
- Memory Client Session
- CRM Lead Service
- Escalation Specialist Layer
- Calendar Booking Service
- Dashboard Deal UI
- Espo Lead Store
- Inventory Tool Dispatch
- Frontend Dependencies
- Espo CRM Client
- Mobile App Config
- Deal Negotiation Models
- Frontend API Client
- Deal Pricing Engine
- Deal Desk Agent
- Language Settings Tests
- Mobile Call Screen
- Deal Authority Engine
- Session Summary Builder
- Web Home Page
- Activity and Tool UI
- LLM Pipeline Core
- RTM Event Publisher
- Call Stage UI
- Inventory Product Store
- Call Capacity Metrics
- Agora RTC Client
- LLM Endpoint Tests
- Task Management Service
- Language Voice Profiles
- LLM Provider Adapters
- 3D Avatar and Orb
- Handoff Summary Tests
- Booking Notification Tests
- Frontend TypeScript Config
- Calendar and Tool Executor
- CRM Store Persistence
- LLM Benchmarking Scripts
- Bridge Line Orchestration
- Espo Calendar Client
- Handoff Delivery Routes
- Spoken Bridge Lines
- Concurrency Load Testing
- Mobile Settings Screen
- Call Transcript UI
- Mobile Agora Client
- LLM Memory Pipeline Tests
- About Page Brand Marks
- Mobile Theme Layout
- EspoCRM Provisioning Script
- Core Domain Models
- Booking Notification Service
- Icon Generation Script
- Agora REST Client
- RAG Retriever and Search
- Dashboard Auth Routes
- EspoCRM Environment Config
- EspoCRM Environment Config
- Inventory Search Ranking
- Agent Time Savings
- ICS Invite Builder
- Keyword RAG Index
- Mobile Escalations Screen
- Calendar Slot Store
- Inventory Stock Lookup
- RAG Corpus Ingestion
- CORS and Lead Update Tests
- Backend Service Compose
- MariaDB Service Config
- Caddy Proxy Config
- MariaDB Service Config
- Call Brief UI
- Concurrent Store Tests
- EspoCRM Service Compose
- EspoCRM Service Compose
- EspoCRM Error Handling
- EspoCRM WebSocket Service
- Docker Volumes Config
- Mobile Scripts Config
- Mobile TypeScript Config
- Scripted LLM Test Client
- Gemini LLM Adapter
- Docker Compose Volumes
- EspoCRM Daemon Service
- Production Frontend Compose
- EspoCRM Daemon Service
- EspoCRM WebSocket Service
- Handoff Card UI
- Lead Card UI
- Service Healthcheck Config
- Frontend Build Config
- Service Healthcheck Config
- Next.js App Layout
- Fallback Chat Client
- Test Fixtures Reset
- ASGI Exception Middleware
- Next.js Config
- Prompt String Formatting Tests
- Profile Completeness Validation
- Sarvam Cross-Lingual Speaker
- Bootstrap Script
- Startup Script
- MCP Agora Docs Config

## God Nodes (most connected - your core abstractions)
1. `SessionState` - 69 edges
2. `get_settings()` - 61 edges
3. `Settings` - 56 edges
4. `dispatch()` - 47 edges
5. `Lead` - 37 edges
6. `LLMTurn` - 36 edges
7. `Home()` - 34 edges
8. `RightBrain` - 33 edges
9. `useTheme()` - 31 edges
10. `CalendarStore` - 30 edges

## Surprising Connections (you probably didn't know these)
- `run_pipeline_mode()` --uses--> `TranscriptTurn`  [INFERRED]
  scripts/capacity_test.py → backend/app/escalation/models.py
- `one_call()` --calls--> `TranscriptTurn`  [INFERRED]
  scripts/capacity_test.py → backend/app/escalation/models.py
- `main()` --uses--> `Settings`  [INFERRED]
  scripts/bench_llm.py → backend/app/config.py
- `use_hermetic_settings()` --uses--> `Settings`  [INFERRED]
  scripts/capacity_test.py → backend/app/config.py
- `run_pipeline_mode()` --uses--> `SessionState`  [INFERRED]
  scripts/capacity_test.py → backend/app/sessions/models.py

## Import Cycles
- None detected.

## Communities (116 total, 22 thin omitted)

### Community 0 - "Human Inbox Management"
Cohesion: 0.06
Nodes (46): Inbox, EscalationBrief, EscalationRecord, TranscriptTurn, format_slack_message(), notify_slack(), escalate(), AnthropicSummarizerClient (+38 more)

### Community 1 - "Mobile App Dependencies"
Cohesion: 0.04
Nodes (63): dependencies, expo@~57.0.20, expo-blur@~57.0.2, expo-build-properties@~57.0.17, expo-constants@~57.0.17, expo-dev-client@~57.0.18, expo-device@~57.0.1, expo-font@~57.0.3 (+55 more)

### Community 2 - "Agora Join Payload Builder"
Cohesion: 0.07
Nodes (29): _build_asr_params(), _build_filler_words(), build_join_payload(), _build_tts_params(), profile_for(), warn_on_language_overrides(), Settings, strip_speech_markup() (+21 more)

### Community 3 - "Background Tasks Config"
Cohesion: 0.07
Nodes (18): run_in_background(), get_settings(), _build_store(), chat_completions(), ChatCompletionsRequest, ChatMessage, _history_from_openai_messages(), _latest_user_text() (+10 more)

### Community 4 - "RTC Token and Call API"
Cohesion: 0.08
Nodes (21): build_rtc_token(), build_rtm_token(), end_call(), session_events(), start_call(), _default_rtm_token_builder(), _default_token_builder(), end_call() (+13 more)

### Community 5 - "Espo Calendar Store"
Cohesion: 0.09
Nodes (18): EspoCalendarStore, to_espo_datetime(), _client(), test_availability_marks_slots_taken_by_existing_meetings(), handler(), test_aware_datetimes_are_converted_not_truncated(), test_booking_an_unknown_slot_is_an_error(), test_booking_creates_a_meeting_with_an_assignee() (+10 more)

### Community 6 - "Voice Direction Layer"
Cohesion: 0.06
Nodes (24): agent_for_tools(), ensure_voice(), script_language(), live_call(), _now(), RecordingClient, test_a_call_with_no_agent_yet_is_a_no_op(), test_a_failed_switch_never_reaches_the_turn() (+16 more)

### Community 7 - "Handoff and Admin Service"
Cohesion: 0.08
Nodes (25): all_summaries(), get(), healthz(), ApprovalRequest, approve_discount(), capacity_metrics(), _client_key(), create_product() (+17 more)

### Community 8 - "Memory Client Session"
Cohesion: 0.08
Nodes (20): build_config(), get_memory(), is_configured(), recall(), safe_recall(), safe_write_back(), write_back(), VoyageEmbedding (+12 more)

### Community 9 - "CRM Lead Service"
Cohesion: 0.10
Nodes (18): add_note(), get_lead(), list_leads(), _now(), qualify_lead(), set_outcome(), sync_left_brain(), upsert_lead() (+10 more)

### Community 10 - "Escalation Specialist Layer"
Cohesion: 0.08
Nodes (18): _build_prompt(), consult(), heuristic_answer(), LLMSpecialistClient, SolutionsAnswer, SpecialistClient, _ask_solutions_engineer(), _engineer_returning() (+10 more)

### Community 11 - "Calendar Booking Service"
Cohesion: 0.15
Nodes (20): Booking, BookingNotFoundError, SlotTakenError, _as_utc(), book(), cancel(), list_available(), reschedule() (+12 more)

### Community 12 - "Dashboard Deal UI"
Cohesion: 0.12
Nodes (33): ApproveDiscountRow(), DashboardPage(), emptyDraft, DealCard(), DealConcession, DealQuote, DealRound, moneyIn() (+25 more)

### Community 13 - "Espo Lead Store"
Cohesion: 0.09
Nodes (11): EspoLeadStore, _from_espo(), _to_espo(), Lead, test_create_response_name_field_is_not_trusted(), test_crm_write_failure_never_propagates(), test_industry_writes_and_reads_as_espos_stock_field(), test_lead_always_carries_a_last_name() (+3 more)

### Community 14 - "Inventory Tool Dispatch"
Cohesion: 0.11
Nodes (25): InventoryUnavailable, dispatch(), _session(), test_in_stock_answer_carries_the_exact_number(), test_out_of_stock_answer_carries_the_lead_time(), test_out_of_stock_names_real_alternatives_not_invented_ones(), test_quantity_shortfall_is_reported_not_rounded_up(), test_quantity_that_fits_is_confirmed() (+17 more)

### Community 15 - "Frontend Dependencies"
Cohesion: 0.08
Nodes (34): dependencies, agora-agent-client-toolkit@^2.9.0, agora-rtm-sdk@^2.3.0, react@^18.3.0, react-dom@^18.3.0, three@^0.153.0, devDependencies, @types/node@^22.0.0 (+26 more)

### Community 16 - "Espo CRM Client"
Cohesion: 0.09
Nodes (7): _build_store(), EspoClient, EspoTaskStore, _from_espo(), _to_espo(), _build_store(), test_task_writes_to_espos_stock_task_entity()

### Community 17 - "Mobile App Config"
Cohesion: 0.06
Nodes (32): backgroundColor, backgroundImage, foregroundImage, monochromeImage, adaptiveIcon, package, permissions, predictiveBackGestureEnabled (+24 more)

### Community 18 - "Deal Negotiation Models"
Cohesion: 0.15
Nodes (20): DeskProposal, Commitment, _render_call_state(), _render_negotiation(), _consult_returning(), StubDesk, test_a_human_approval_reaches_the_live_call(), test_a_modest_ask_is_authorised_by_zuno_alone() (+12 more)

### Community 19 - "Frontend API Client"
Cohesion: 0.09
Nodes (27): CallSummary, endCall(), EndCallResponse, EscalationBrief, EscalationKind, fetchHandoff(), fetchSessionEvents(), HandoffDetails (+19 more)

### Community 20 - "Deal Pricing Engine"
Cohesion: 0.11
Nodes (18): build_offer(), build_quote(), discount_for_target(), _fmt(), _money(), price_summary(), Concession, DeviceLine (+10 more)

### Community 21 - "Deal Desk Agent"
Cohesion: 0.10
Nodes (13): _build_prompt(), consult(), DeskClient, heuristic_proposal(), LLMDeskClient, _strip_fence(), _system_prompt(), volume_tier() (+5 more)

### Community 22 - "Language Settings Tests"
Cohesion: 0.10
Nodes (16): _props(), test_a_typo_in_the_language_costs_the_wrong_language_not_a_dead_call(), test_agora_speaks_the_profiles_filler_phrases_not_the_english_ones(), test_an_explicit_sarvam_speaker_still_wins_over_the_profile(), test_an_explicit_setting_still_wins_over_the_profile(), test_english_stays_exactly_as_it_was(), test_hindi_switches_the_recogniser_and_the_target_language_together(), test_hinglish_pins_sarvam_to_english_since_there_is_no_auto_mode() (+8 more)

### Community 23 - "Mobile Call Screen"
Cohesion: 0.16
Nodes (22): Brief(), Header(), RepCallScreen(), CallScreen(), EndCard(), HandoffBanner(), Status, Caption() (+14 more)

### Community 24 - "Deal Authority Engine"
Cohesion: 0.10
Nodes (16): authorise(), authority_for(), round_ceiling(), normalise_model(), test_a_discount_is_never_clawed_back(), test_a_discount_with_nothing_asked_in_return_is_cut_back(), test_a_human_approval_is_still_a_ceiling(), test_a_human_approval_outranks_the_desk_ceiling() (+8 more)

### Community 25 - "Session Summary Builder"
Cohesion: 0.13
Nodes (14): _agreed(), build(), _DefaultClient, _duration_seconds(), _facts(), heuristic_summary(), LLMClient, _owed() (+6 more)

### Community 26 - "Web Home Page"
Cohesion: 0.14
Nodes (23): CallStatus, EndIcon(), fmt(), Home(), icon, MicIcon(), nextId(), PauseIcon() (+15 more)

### Community 27 - "Activity and Tool UI"
Cohesion: 0.14
Nodes (23): ActivityCard(), stamp(), ToolRecord, DoodleCircle(), DoodleLoop(), firstStringArg(), POPUP_TOOLS, ToolPopup() (+15 more)

### Community 28 - "LLM Pipeline Core"
Cohesion: 0.15
Nodes (10): ChatLLMClient, default_llm_client(), StreamingChatLLMClient, _build_system_prompt(), _execute_tool_calls(), _history_to_anthropic_messages(), run_turn(), run_turn_stream() (+2 more)

### Community 29 - "RTM Event Publisher"
Cohesion: 0.14
Nodes (8): AgoraRtmPublisher, CompositePublisher, default_rtm_publisher(), SessionEventRecorder, test_agora_rtm_publisher_posts_to_correct_url_and_swallows_errors(), test_composite_publisher_continues_after_one_member_raises(), test_default_rtm_publisher_falls_back_to_logging_when_unconfigured(), test_default_rtm_publisher_fans_out_to_recorder_and_agora_when_configured()

### Community 30 - "Call Stage UI"
Cohesion: 0.14
Nodes (19): Stage, EASING, EASING, REACT, Ring(), RINGS, Rings(), EASING (+11 more)

### Community 31 - "Inventory Product Store"
Cohesion: 0.12
Nodes (8): Product, EspoProductStore, _from_espo(), MemoryProductStore, test_espo_row_maps_with_unprefixed_field_names(), test_product_can_fulfil_rejects_zero_quantity(), test_products_are_copied_so_a_caller_cannot_mutate_the_seed_set(), test_status_is_derived_when_the_row_leaves_it_blank()

### Community 32 - "Call Capacity Metrics"
Cohesion: 0.17
Nodes (13): _duration_seconds(), peak_concurrency(), snapshot(), _call(), test_a_call_ending_exactly_as_another_starts_is_not_an_overlap(), test_a_still_running_call_counts_up_to_now(), test_an_empty_deployment_reports_zeros_rather_than_dividing_by_zero(), test_capacity_is_readable_over_http() (+5 more)

### Community 33 - "Agora RTC Client"
Cohesion: 0.12
Nodes (10): AgoraCallClient, CallCallbacks, normalizeRole(), RawTranscriptTurn, RtmCustomEvent, stripSpeechMarkup(), TranscriptEvent, StartCallResponse (+2 more)

### Community 34 - "LLM Endpoint Tests"
Cohesion: 0.24
Nodes (13): LLMTurn, _patch_llm_client(), _post(), ScriptedLLMClient, test_all_blank_turns_skips_llm_entirely(), test_blank_content_turns_are_dropped_not_sent_to_llm(), test_forced_escalation_fires_when_llm_never_calls_the_tool(), test_guardrails_off_by_default_do_not_force_escalation() (+5 more)

### Community 35 - "Task Management Service"
Cohesion: 0.20
Nodes (8): Task, create_task(), list_tasks(), TaskStore, test_tasks_endpoint_lists_a_created_followup(), test_create_task_persists_note_and_due(), test_due_is_optional(), test_tasks_from_different_sessions_all_list_together()

### Community 36 - "Language Voice Profiles"
Cohesion: 0.16
Nodes (8): default_agora_client(), get_profile(), LanguageProfile, follow(), resolve_sarvam_target(), resolve_voice(), voice_for_language(), main()

### Community 37 - "LLM Provider Adapters"
Cohesion: 0.17
Nodes (7): AnthropicChatClient, _gemini_parts_to_turn(), GroqChatClient, _parse_arguments(), ToolCall, _tools_to_gemini(), _tools_to_openai()

### Community 38 - "3D Avatar and Orb"
Cohesion: 0.17
Nodes (13): Avatar3D(), findMorphMeshes(), MORPH_MESH_NAMES, VISEMES, hex(), Orb(), PALETTE, Phase (+5 more)

### Community 39 - "Handoff Summary Tests"
Cohesion: 0.15
Nodes (11): BrokenSummarizer, finished_call(), StubSummarizer, test_a_dead_summariser_still_produces_a_usable_wrap_up(), test_a_nonsense_urgency_falls_back_rather_than_being_stored(), test_slack_failure_does_not_cost_the_crm_note(), test_the_crm_always_gets_it_even_with_nothing_configured(), test_the_facts_come_off_the_record_not_the_transcript() (+3 more)

### Community 40 - "Booking Notification Tests"
Cohesion: 0.27
Nodes (13): Recorder, _session_with_lead(), _settings(), _slot(), test_booking_records_the_slot_id_for_the_call_end_hook(), test_call_end_hook_survives_an_unresolvable_slot(), test_confirmation_carries_both_inline_invite_and_attachment(), test_disabled_sends_nothing() (+5 more)

### Community 41 - "Frontend TypeScript Config"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+10 more)

### Community 42 - "Calendar and Tool Executor"
Cohesion: 0.14
Nodes (7): slot_label(), _calendar_check_availability(), _crm_qualify_lead(), _dt(), _log_objection(), _schedule_followup(), _search_pricing_rag()

### Community 43 - "CRM Store Persistence"
Cohesion: 0.17
Nodes (5): _now(), _build_store(), load_state(), save_state(), _state_dir()

### Community 44 - "LLM Benchmarking Scripts"
Cohesion: 0.20
Nodes (5): _messages_to_openai(), bench(), main(), _percentile(), main()

### Community 45 - "Bridge Line Orchestration"
Cohesion: 0.15
Nodes (6): speakable_tool(), test_bookkeeping_tools_stay_silent(), test_escalation_is_never_bridged(), test_speakable_tool_none_when_nothing_is_worth_narrating(), test_speakable_tool_picks_the_lookup_out_of_a_batched_hop(), test_the_deal_desk_wait_is_narrated()

### Community 46 - "Espo Calendar Client"
Cohesion: 0.16
Nodes (5): _grid(), slot_id_for(), from_espo_datetime(), test_datetime_round_trip_comes_back_aware(), test_slot_ids_are_deterministic()

### Community 47 - "Handoff Delivery Routes"
Cohesion: 0.23
Nodes (9): deliver(), _settings(), to_crm(), to_email(), to_slack(), CallSummary, on_call_end(), test_as_text_is_one_account_of_the_call_for_all_three_routes() (+1 more)

### Community 48 - "Spoken Bridge Lines"
Cohesion: 0.12
Nodes (8): line_for(), test_lines_are_short_and_free_of_markdown(), test_lines_vary_so_the_agent_does_not_repeat_one_phrase(), test_lookup_tools_get_a_line(), test_an_untranslated_tool_falls_back_to_english_rather_than_dead_air(), test_bridge_lines_keep_the_speech_markup_in_every_language(), test_every_language_covers_every_tool_the_customer_waits_on(), test_hindi_bridge_lines_are_devanagari_not_romanised()

### Community 49 - "Concurrency Load Testing"
Cohesion: 0.21
Nodes (8): main(), _percentile(), _report(), run_live_mode(), run_pipeline_mode(), one_call(), StubDesk, use_hermetic_settings()

### Community 50 - "Mobile Settings Screen"
Cohesion: 0.27
Nodes (14): Section(), SettingsScreen(), PrimaryButton(), loadApiBase(), ping(), setApiBase(), DEFAULT_BASE_URL, getBaseUrl() (+6 more)

### Community 51 - "Call Transcript UI"
Cohesion: 0.22
Nodes (13): CallPhase, Pill(), Tone, NoteRow(), Row, TranscriptSheet(), TurnRow(), sans (+5 more)

### Community 52 - "Mobile Agora Client"
Cohesion: 0.16
Nodes (5): AgoraCall, aiAudioParams(), CallHandlers, JoinParams, Levels

### Community 53 - "LLM Memory Pipeline Tests"
Cohesion: 0.19
Nodes (6): LoggingPublisher, RtmEvent, RecordingLLMClient, test_no_recalled_memories_leaves_system_prompt_unmodified(), test_recalled_memories_are_injected_into_system_prompt(), test_write_back_receives_user_and_final_assistant_text()

### Community 54 - "About Page Brand Marks"
Cohesion: 0.30
Nodes (12): AboutPage(), metadata, CaddyMark, DeepgramMark, DockerMark, ExpoMark, FastApiMark, GeminiMark (+4 more)

### Community 55 - "Mobile Theme Layout"
Cohesion: 0.19
Nodes (8): Chrome(), RootLayout(), getThemeMode(), setThemeMode(), ThemeContext, ThemeContextValue, ThemeProvider(), expo-router

### Community 56 - "EspoCRM Provisioning Script"
Cohesion: 0.20
Nodes (5): _ensure_inventory(), _find_one(), _install_layout(), main(), _request()

### Community 58 - "Booking Notification Service"
Cohesion: 0.21
Nodes (7): _body(), on_booking(), on_call_end(), _recap_lines(), _resolve_settings(), send_booking_confirmation(), _sender()

### Community 59 - "Icon Generation Script"
Cohesion: 0.19
Nodes (10): sharp@^0.35.4, here, loadMark(), main(), out, render(), repo, square() (+2 more)

### Community 61 - "RAG Retriever and Search"
Cohesion: 0.21
Nodes (5): get_index(), reset_index(), search(), SearchResult, test_create_product_appears_in_list_and_is_searchable()

### Community 62 - "Dashboard Auth Routes"
Cohesion: 0.24
Nodes (8): _client(), test_a_stray_or_tampered_cookie_is_rejected(), test_a_successful_login_clears_the_failure_count(), test_capacity_and_calendar_never_need_a_session(), test_dashboard_endpoints_reject_missing_or_wrong_session(), test_login_then_dashboard_endpoints_succeed(), test_no_password_required_when_unset(), test_repeated_failed_logins_are_rate_limited()

### Community 63 - "EspoCRM Environment Config"
Cohesion: 0.18
Nodes (13): ESPOCRM_ADMIN_PASSWORD, ESPOCRM_ADMIN_USERNAME, ESPOCRM_CONFIG_USE_WEB_SOCKET, ESPOCRM_CONFIG_WEB_SOCKET_URL, ESPOCRM_CONFIG_WEB_SOCKET_ZERO_M_Q_SUBMISSION_DSN, ESPOCRM_CONFIG_WEB_SOCKET_ZERO_M_Q_SUBSCRIBER_DSN, ESPOCRM_DATABASE_HOST, ESPOCRM_DATABASE_PASSWORD (+5 more)

### Community 64 - "EspoCRM Environment Config"
Cohesion: 0.18
Nodes (13): ESPOCRM_ADMIN_PASSWORD, ESPOCRM_ADMIN_USERNAME, ESPOCRM_CONFIG_USE_WEB_SOCKET, ESPOCRM_CONFIG_WEB_SOCKET_URL, ESPOCRM_CONFIG_WEB_SOCKET_ZERO_M_Q_SUBMISSION_DSN, ESPOCRM_CONFIG_WEB_SOCKET_ZERO_M_Q_SUBSCRIBER_DSN, ESPOCRM_DATABASE_HOST, ESPOCRM_DATABASE_PASSWORD (+5 more)

### Community 65 - "Inventory Search Ranking"
Cohesion: 0.30
Nodes (6): _normalise(), rank(), score(), _tokens(), _weight(), _weights()

### Community 66 - "Agent Time Savings"
Cohesion: 0.21
Nodes (6): admin_minutes(), agent_minutes(), total_minutes(), test_an_escalation_saves_no_human_time(), test_repeated_data_entry_is_counted_once_but_lookups_are_not(), test_talk_time_and_paperwork_are_reported_apart()

### Community 67 - "ICS Invite Builder"
Cohesion: 0.24
Nodes (7): build_invite(), escape_text(), fold(), _utc_stamp(), test_invite_escapes_text_values(), test_invite_is_a_request_with_utc_times_and_crlf(), test_long_lines_fold_without_splitting_a_codepoint()

### Community 68 - "Keyword RAG Index"
Cohesion: 0.30
Nodes (7): KeywordIndex, _tokenize(), top_score(), test_corpus_loads_all_docs(), test_search_competitor_query_returns_comparison_doc(), test_search_irrelevant_query_returns_low_or_no_score(), test_search_pricing_query_returns_pricing_content()

### Community 69 - "Mobile Escalations Screen"
Cohesion: 0.27
Nodes (10): EscalationsScreen(), Row(), EscalationRecord, fetchInbox(), getRepUnlocked(), useInboxPoll(), useRepUnlocked(), timeAgo() (+2 more)

### Community 71 - "Inventory Stock Lookup"
Cohesion: 0.20
Nodes (6): find(), in_stock_alternatives(), _check_inventory(), test_ambiguous_query_reports_the_other_contender(), test_matches_what_a_caller_would_actually_say(), test_products_we_do_not_stock_are_a_miss_not_a_wrong_row()

### Community 72 - "RAG Corpus Ingestion"
Cohesion: 0.31
Nodes (5): build_corpus(), Chunk, _chunk_markdown(), _chunk_pricing_json(), load_documents()

### Community 74 - "Backend Service Compose"
Cohesion: 0.18
Nodes (11): container_name, depends_on, env_file, environment, restart, volumes, espocrm, ESPOCRM_BASE_URL (+3 more)

### Community 75 - "MariaDB Service Config"
Cohesion: 0.20
Nodes (10): MARIADB_DATABASE, MARIADB_PASSWORD, MARIADB_ROOT_PASSWORD, MARIADB_USER, container_name, environment, image, restart (+2 more)

### Community 76 - "Caddy Proxy Config"
Cohesion: 0.20
Nodes (10): container_name, depends_on, environment, image, ports, restart, volumes, ZUNO_CRM_DOMAIN (+2 more)

### Community 77 - "MariaDB Service Config"
Cohesion: 0.20
Nodes (10): MARIADB_DATABASE, MARIADB_PASSWORD, MARIADB_ROOT_PASSWORD, MARIADB_USER, container_name, environment, image, restart (+2 more)

### Community 78 - "Call Brief UI"
Cohesion: 0.27
Nodes (9): Brief(), fmt(), List(), MOOD_Y, Stat(), URGENCY, CallSummary, RightBrain (+1 more)

### Community 79 - "Concurrent Store Tests"
Cohesion: 0.22
Nodes (4): _hammer(), test_concurrent_calls_do_not_corrupt_the_calendar_store(), test_concurrent_calls_do_not_corrupt_the_lead_store(), test_concurrent_calls_do_not_corrupt_the_session_store()

### Community 80 - "EspoCRM Service Compose"
Cohesion: 0.22
Nodes (9): espocrm-db, container_name, condition, depends_on, image, ports, restart, volumes (+1 more)

### Community 81 - "EspoCRM Service Compose"
Cohesion: 0.22
Nodes (9): espocrm-db, container_name, condition, depends_on, image, ports, restart, volumes (+1 more)

### Community 82 - "EspoCRM Error Handling"
Cohesion: 0.29
Nodes (4): EspoCRMError, test_client_surfaces_the_status_reason_header(), test_espo_store_raises_rather_than_returning_an_empty_catalogue(), list()

### Community 83 - "EspoCRM WebSocket Service"
Cohesion: 0.25
Nodes (8): container_name, depends_on, entrypoint, image, ports, restart, volumes, espocrm-websocket

### Community 84 - "Docker Volumes Config"
Cohesion: 0.25
Nodes (8): volumes, backend-state, caddy-config, caddy-data, espocrm-client-custom, espocrm-custom, espocrm-data, espocrm-db

### Community 85 - "Mobile Scripts Config"
Cohesion: 0.25
Nodes (8): scripts, android, icons, ios, lint, reset-project, start, web

### Community 86 - "Mobile TypeScript Config"
Cohesion: 0.25
Nodes (7): compilerOptions, paths, strict, extends, include, @/assets/*, expo/tsconfig.base

### Community 89 - "Docker Compose Volumes"
Cohesion: 0.29
Nodes (6): services, volumes, espocrm-client-custom, espocrm-custom, espocrm-data, espocrm-db

### Community 90 - "EspoCRM Daemon Service"
Cohesion: 0.29
Nodes (7): container_name, depends_on, entrypoint, image, restart, volumes, espocrm-daemon

### Community 91 - "Production Frontend Compose"
Cohesion: 0.29
Nodes (6): container_name, depends_on, restart, name, services, frontend

### Community 92 - "EspoCRM Daemon Service"
Cohesion: 0.29
Nodes (7): container_name, depends_on, entrypoint, image, restart, volumes, espocrm-daemon

### Community 93 - "EspoCRM WebSocket Service"
Cohesion: 0.29
Nodes (7): container_name, depends_on, entrypoint, image, restart, volumes, espocrm-websocket

### Community 94 - "Handoff Card UI"
Cohesion: 0.43
Nodes (6): DoodleWave(), Escalation, EscalationBrief, Guard(), HandoffCard(), JoinLink()

### Community 95 - "Lead Card UI"
Cohesion: 0.38
Nodes (6): LeadCard(), useTween(), LeadEdit, updateLeadManually(), OUTCOME_LABEL, STAGES

### Community 96 - "Service Healthcheck Config"
Cohesion: 0.33
Nodes (6): healthcheck, interval, retries, start_period, test, timeout

### Community 97 - "Frontend Build Config"
Cohesion: 0.40
Nodes (6): NEXT_PUBLIC_BACKEND_URL, build, args, context, dockerfile, build

### Community 98 - "Service Healthcheck Config"
Cohesion: 0.33
Nodes (6): healthcheck, interval, retries, start_period, test, timeout

### Community 99 - "Next.js App Layout"
Cohesion: 0.33
Nodes (3): metadata, next@^15.0.0, next

## Knowledge Gaps
- **1 isolated node(s):** `expo/tsconfig.base`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 763 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_settings()` connect `Background Tasks Config` to `Human Inbox Management`, `Agora Join Payload Builder`, `RTC Token and Call API`, `Voice Direction Layer`, `Handoff and Admin Service`, `Memory Client Session`, `Espo Lead Store`, `Espo CRM Client`, `LLM Pipeline Core`, `RTM Event Publisher`, `Language Voice Profiles`, `LLM Provider Adapters`, `Calendar and Tool Executor`, `CRM Store Persistence`, `Bridge Line Orchestration`, `Handoff Delivery Routes`, `Spoken Bridge Lines`, `Booking Notification Service`, `Agora REST Client`, `Calendar Slot Store`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Are the 30 inferred relationships involving `SessionState` (e.g. with `_agreed()` and `build()`) actually correct?**
  _`SessionState` has 30 INFERRED edges - model-reasoned connections that need verification._
- **What connects `expo/tsconfig.base` to the rest of the system?**
  _1 weakly-connected nodes found - possible missing edges._
- **Should `Human Inbox Management` be split into smaller, more focused modules?**
  _Cohesion score 0.05696636925188744 - nodes in this community are weakly interconnected._
- **Why does `SessionState` connect `Session Summary Builder` to `Call Capacity Metrics`, `Human Inbox Management`, `Background Tasks Config`, `RTC Token and Call API`, `Voice Direction Layer`, `Handoff and Admin Service`, `Handoff Summary Tests`, `Booking Notification Tests`, `Escalation Specialist Layer`, `Inventory Tool Dispatch`, `Handoff Delivery Routes`, `Concurrent Store Tests`, `Concurrency Load Testing`, `Deal Negotiation Models`, `LLM Memory Pipeline Tests`, `Core Domain Models`, `Booking Notification Service`, `LLM Pipeline Core`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `Settings` (e.g. with `_build_asr_params()` and `_build_filler_words()`) actually correct?**
  _`Settings` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Should `Mobile App Dependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.0441468253968254 - nodes in this community are weakly interconnected._