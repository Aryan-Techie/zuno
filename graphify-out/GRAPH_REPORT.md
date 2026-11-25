# Graph Report - zuno  (2026-11-25)

## Corpus Check
- 250 files · ~399,693 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 18 file(s) not represented in the graph (top: (none) 7, .example 4, .css 3)

## Summary
- 2926 nodes · 7179 edges · 133 communities (102 shown, 31 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 442 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d97cb927`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- sessions/models.py
- FakeNotion
- Settings
- get_settings
- controller.py
- graph.py
- Voice Direction Layer
- Handoff and Admin Service
- Memory Client Session
- crm/service.py
- Escalation Specialist Layer
- CalendarStore
- Dashboard Deal UI
- Espo Lead Store
- scrape_dior.py
- frontend/package.json
- handoff/service.py
- Mobile App Config
- Deal Negotiation Models
- src/lib/api.ts
- boutique.py
- Deal Desk Agent
- Language Settings Tests
- Mobile Call Screen
- Deal Authority Engine
- build
- Web Home Page
- Activity and Tool UI
- publisher.py
- chat_completions
- build_invite
- test_inventory.py
- test_capacity.py
- Agora RTC Client
- LLMTurn
- Task Management Service
- NotionClient
- steps
- 3D Avatar and Orb
- catalog.ts
- test_notify.py
- Frontend TypeScript Config
- CatalogIndex
- RightBrain
- llm_client.py
- Bridge Line Orchestration
- test_handoff_summary.py
- AgoraRestClient
- notify/service.py
- json
- settings.tsx
- NotionMirror
- Mobile Agora Client
- catch_all_exceptions
- About Page Brand Marks
- records.py
- mobile/package.json
- Icon Generation Script
- test_notion_sync.py
- [id].tsx
- EspoCRM Environment Config
- EspoCRM Environment Config
- delivery.py
- notion/schema.py
- retriever.py
- ref_react
- provision.py
- json
- ProductViewer3D.tsx
- Backend Service Compose
- MariaDB Service Config
- Caddy Proxy Config
- MariaDB Service Config
- Brief.tsx
- pipeline.py
- EspoCRM Service Compose
- EspoCRM Service Compose
- test_espo_crm.py
- EspoCRM WebSocket Service
- Docker Volumes Config
- Mobile Scripts Config
- Mobile TypeScript Config
- test_knowledge_graph.py
- Docker Compose Volumes
- EspoCRM Daemon Service
- Production Frontend Compose
- EspoCRM Daemon Service
- EspoCRM WebSocket Service
- executor.py
- Service Healthcheck Config
- Frontend Build Config
- Service Healthcheck Config
- fastapi_testclient
- SessionState
- catalogs/catalog.py
- Next.js Config
- NotionSettings
- test_perfume_mode.py
- test_mode_endpoints.py
- Bootstrap Script
- Startup Script
- .mcp.json
- savings.py
- SessionState
- json
- perfume_support.py
- HandoffCard.tsx
- tools_for
- cohost.sh
- RtmEvent
- escalate
- handoff.py

## God Nodes (most connected - your core abstractions)
1. `SessionState` - 101 edges
2. `Settings` - 65 edges
3. `get_settings()` - 63 edges
4. `dispatch()` - 63 edges
5. `LLMTurn` - 51 edges
6. `FakeNotion` - 46 edges
7. `Home()` - 45 edges
8. `Lead` - 39 edges
9. `NotionClient` - 39 edges
10. `TranscriptTurn` - 33 edges

## Surprising Connections (you probably didn't know these)
- `bench()` --calls--> `_tools_to_openai()`  [INFERRED]
  scripts/bench_llm.py → backend/app/orchestrator/llm_client.py
- `bench()` --calls--> `_messages_to_openai()`  [INFERRED]
  scripts/bench_llm.py → backend/app/orchestrator/llm_client.py
- `main()` --uses--> `NotionError`  [INFERRED]
  scripts/setup_notion.py → backend/app/notion/client.py
- `run_pipeline_mode()` --uses--> `TranscriptTurn`  [INFERRED]
  scripts/capacity_test.py → backend/app/escalation/models.py
- `one_call()` --calls--> `TranscriptTurn`  [INFERRED]
  scripts/capacity_test.py → backend/app/escalation/models.py

## Import Cycles
- None detected.

## Communities (133 total, 31 thin omitted)

### Community 0 - "sessions/models.py"
Cohesion: 0.15
Nodes (14): EscalationBrief, EscalationRecord, format_slack_message(), notify_slack(), AnthropicSummarizerClient, _build_prompt(), _default_client(), heuristic_brief() (+6 more)

### Community 1 - "FakeNotion"
Cohesion: 0.05
Nodes (37): NotionError, parse_page_id(), SetupResult, write_env(), _brands(), _client(), FakeClock, test_add_relation_merges_and_skips_noop_writes() (+29 more)

### Community 2 - "Settings"
Cohesion: 0.09
Nodes (26): _build_asr_params(), build_join_payload(), warn_on_language_overrides(), Settings, _client(), test_a_stray_or_tampered_cookie_is_rejected(), test_a_successful_login_clears_the_failure_count(), test_capacity_and_calendar_never_need_a_session() (+18 more)

### Community 3 - "get_settings"
Cohesion: 0.06
Nodes (22): default_agora_client(), build_rtc_token(), build_rtm_token(), get_settings(), healthz(), CallStart, change_mode(), end_call() (+14 more)

### Community 4 - "controller.py"
Cohesion: 0.12
Nodes (14): end_call(), _resolve_outcome(), RtmTokenBuilder, start_call(), TokenBuilder, SessionStore, test_call_end_hook_needs_a_booking(), _fake_token_builder() (+6 more)

### Community 5 - "graph.py"
Cohesion: 0.22
Nodes (13): _build(), exists(), export(), facts_for(), _Graph, _is_code(), _label(), _load() (+5 more)

### Community 6 - "Voice Direction Layer"
Cohesion: 0.06
Nodes (25): agent_for_tools(), ensure_voice(), script_language(), test_director_resolves_the_perfume_voice_only_for_english_zuno(), live_call(), _now(), RecordingClient, test_a_call_with_no_agent_yet_is_a_no_op() (+17 more)

### Community 7 - "Handoff and Admin Service"
Cohesion: 0.10
Nodes (19): ApprovalRequest, approve_discount(), capacity_metrics(), _client_key(), create_product(), dashboard_login(), DashboardLogin, list_inbox() (+11 more)

### Community 8 - "Memory Client Session"
Cohesion: 0.08
Nodes (20): build_config(), get_memory(), is_configured(), recall(), safe_recall(), safe_write_back(), write_back(), VoyageEmbedding (+12 more)

### Community 9 - "crm/service.py"
Cohesion: 0.13
Nodes (16): add_note(), get_lead(), list_leads(), _now(), qualify_lead(), set_outcome(), sync_left_brain(), upsert_lead() (+8 more)

### Community 10 - "Escalation Specialist Layer"
Cohesion: 0.12
Nodes (13): SolutionsAnswer, test_the_engineer_gets_graph_facts_and_the_rule(), complete(), _engineer_returning(), session(), StubEngineer, test_a_broken_engineer_does_not_fail_the_turn(), test_a_confident_search_says_nothing_extra() (+5 more)

### Community 11 - "CalendarStore"
Cohesion: 0.11
Nodes (23): seed_slots(), Booking, BookingNotFoundError, Slot, SlotTakenError, _as_utc(), book(), cancel() (+15 more)

### Community 12 - "Dashboard Deal UI"
Cohesion: 0.09
Nodes (27): GraphPage(), GraphStats(), Stats, View, VIEWS, Logo(), ApiError, CapacitySnapshot (+19 more)

### Community 13 - "Espo Lead Store"
Cohesion: 0.08
Nodes (11): EspoClient, EspoLeadStore, _from_espo(), _to_espo(), Lead, _build_store(), test_industry_writes_and_reads_as_espos_stock_field(), test_lead_status_maps_onto_espos_own_enum() (+3 more)

### Community 14 - "scrape_dior.py"
Cohesion: 0.09
Nodes (30): block_paragraphs(), Browser, build_aliases(), cdn_image(), clean_name(), condense(), demo_stock(), discover() (+22 more)

### Community 15 - "frontend/package.json"
Cohesion: 0.06
Nodes (34): metadata, metadata, dependencies, agora-agent-client-toolkit@^2.9.0, agora-rtm-sdk@^2.3.0, next@^15.0.0, react@^18.3.0, react-dom@^18.3.0 (+26 more)

### Community 16 - "handoff/service.py"
Cohesion: 0.13
Nodes (10): all_summaries(), _emit_call_ended(), get(), on_call_end(), reset(), get_summary(), list_summaries(), reset_global_stores() (+2 more)

### Community 17 - "Mobile App Config"
Cohesion: 0.07
Nodes (29): backgroundColor, backgroundImage, foregroundImage, monochromeImage, adaptiveIcon, package, permissions, predictiveBackGestureEnabled (+21 more)

### Community 18 - "Deal Negotiation Models"
Cohesion: 0.12
Nodes (23): DeskProposal, heuristic_proposal(), Commitment, Concession, test_what_was_already_promised_is_the_section_a_rep_cannot_miss(), _consult_returning(), session(), StubDesk (+15 more)

### Community 19 - "src/lib/api.ts"
Cohesion: 0.09
Nodes (26): endCall(), EndCallResponse, EscalationBrief, EscalationKind, fetchHandoff(), fetchInbox(), fetchSessionEvents(), HandoffDetails (+18 more)

### Community 20 - "boutique.py"
Cohesion: 0.13
Nodes (13): authorise(), _hkd(), _lines(), negotiate(), _price_summary(), _quote(), discount_for_target(), _fmt() (+5 more)

### Community 21 - "Deal Desk Agent"
Cohesion: 0.11
Nodes (11): _build_prompt(), consult(), DeskClient, LLMDeskClient, _strip_fence(), _system_prompt(), round_ceiling(), volume_tier() (+3 more)

### Community 22 - "Language Settings Tests"
Cohesion: 0.07
Nodes (20): _props(), test_a_typo_in_the_language_costs_the_wrong_language_not_a_dead_call(), test_agora_speaks_the_profiles_filler_phrases_not_the_english_ones(), test_an_explicit_sarvam_speaker_still_wins_over_the_profile(), test_an_explicit_setting_still_wins_over_the_profile(), test_english_stays_exactly_as_it_was(), test_every_profile_is_internally_complete(), test_hindi_switches_the_recogniser_and_the_target_language_together() (+12 more)

### Community 23 - "Mobile Call Screen"
Cohesion: 0.10
Nodes (35): react-native@0.86.3, react-native-reanimated@4.5.1, CallScreen(), EndCard(), HandoffBanner(), Status, Caption(), CaptionInput (+27 more)

### Community 24 - "Deal Authority Engine"
Cohesion: 0.08
Nodes (25): authorise(), authority_for(), build_offer(), build_quote(), _money(), normalise_model(), _negotiate_deal(), test_a_discount_is_never_clawed_back() (+17 more)

### Community 25 - "build"
Cohesion: 0.15
Nodes (11): _agreed(), build(), _DefaultClient, _duration_seconds(), _facts(), heuristic_summary(), LLMClient, _owed() (+3 more)

### Community 26 - "Web Home Page"
Cohesion: 0.10
Nodes (36): CallStatus, EndIcon(), fmt(), Home(), icon, MicIcon(), MoonIcon(), nextId() (+28 more)

### Community 27 - "Activity and Tool UI"
Cohesion: 0.12
Nodes (26): ActivityCard(), stamp(), ToolRecord, LeadCard(), useTween(), firstStringArg(), POPUP_TOOLS, ToolPopup() (+18 more)

### Community 28 - "publisher.py"
Cohesion: 0.07
Nodes (13): run_in_background(), _execute_tool_calls(), _turn_to_assistant_content(), AgoraRtmPublisher, CompositePublisher, default_rtm_publisher(), RtmPublisher, SessionEventRecorder (+5 more)

### Community 29 - "chat_completions"
Cohesion: 0.18
Nodes (9): chat_completions(), ChatCompletionsRequest, ChatMessage, _history_from_openai_messages(), _latest_user_text(), _publish_turn(), _sse_chunk(), _stream_response() (+1 more)

### Community 30 - "build_invite"
Cohesion: 0.24
Nodes (7): build_invite(), escape_text(), fold(), _utc_stamp(), test_invite_escapes_text_values(), test_invite_is_a_request_with_utc_times_and_crlf(), test_long_lines_fold_without_splitting_a_codepoint()

### Community 31 - "test_inventory.py"
Cohesion: 0.05
Nodes (32): InventoryUnavailable, Product, find(), in_stock_alternatives(), _normalise(), rank(), score(), _tokens() (+24 more)

### Community 32 - "test_capacity.py"
Cohesion: 0.11
Nodes (17): _duration_seconds(), peak_concurrency(), snapshot(), _call(), _hammer(), test_a_call_ending_exactly_as_another_starts_is_not_an_overlap(), test_a_still_running_call_counts_up_to_now(), test_an_empty_deployment_reports_zeros_rather_than_dividing_by_zero() (+9 more)

### Community 33 - "Agora RTC Client"
Cohesion: 0.12
Nodes (10): AgoraCallClient, CallCallbacks, normalizeRole(), RawTranscriptTurn, RtmCustomEvent, stripSpeechMarkup(), TranscriptEvent, StartCallResponse (+2 more)

### Community 34 - "LLMTurn"
Cohesion: 0.13
Nodes (16): AnthropicChatClient, LLMTurn, ToolCall, _patch_llm_client(), _post(), ScriptedLLMClient, test_all_blank_turns_skips_llm_entirely(), test_blank_content_turns_are_dropped_not_sent_to_llm() (+8 more)

### Community 35 - "Task Management Service"
Cohesion: 0.09
Nodes (17): EspoCRMError, EspoTaskStore, _from_espo(), _to_espo(), Task, create_task(), list_tasks(), _build_store() (+9 more)

### Community 36 - "NotionClient"
Cohesion: 0.09
Nodes (7): is_trashed(), NotionClient, DatabaseRef, Provisioner, DatabaseSpec, _args(), main()

### Community 37 - "steps"
Cohesion: 0.10
Nodes (20): BASE, GH_TOKEN, runs-on, steps, jobs, impact, name, on (+12 more)

### Community 38 - "3D Avatar and Orb"
Cohesion: 0.16
Nodes (14): Avatar3D(), findMorphMeshes(), MORPH_MESH_NAMES, VISEMES, hex(), Orb(), PALETTE, PERFUME_PALETTE (+6 more)

### Community 39 - "catalog.ts"
Cohesion: 0.17
Nodes (31): CatalogBrowser(), CatalogCard(), CATEGORY_ORDER, Load, ProductModal(), DeviceGlyph(), glyph, KeyIngredients() (+23 more)

### Community 40 - "test_notify.py"
Cohesion: 0.33
Nodes (12): Recorder, _session_with_lead(), _settings(), _slot(), test_call_end_hook_survives_an_unresolvable_slot(), test_confirmation_carries_both_inline_invite_and_attachment(), test_disabled_sends_nothing(), test_failed_send_leaves_the_backstop_free_to_retry() (+4 more)

### Community 41 - "Frontend TypeScript Config"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+10 more)

### Community 43 - "RightBrain"
Cohesion: 0.17
Nodes (17): check_triggers(), frustration_streak(), low_rag_confidence(), objection_retry_exceeded(), Objection, RightBrain, test_check_triggers_low_confidence_only(), test_check_triggers_no_escalation_when_healthy() (+9 more)

### Community 44 - "llm_client.py"
Cohesion: 0.09
Nodes (13): ChatLLMClient, default_llm_client(), FallbackChatClient, _gemini_parts_to_turn(), GeminiChatClient, GroqChatClient, _messages_to_gemini(), _messages_to_openai() (+5 more)

### Community 45 - "Bridge Line Orchestration"
Cohesion: 0.08
Nodes (15): line_for(), speakable_tool(), test_bookkeeping_tools_stay_silent(), test_escalation_is_never_bridged(), test_lines_are_short_and_free_of_markdown(), test_lines_vary_so_the_agent_does_not_repeat_one_phrase(), test_lookup_tools_get_a_line(), test_speakable_tool_none_when_nothing_is_worth_narrating() (+7 more)

### Community 46 - "test_handoff_summary.py"
Cohesion: 0.16
Nodes (11): BrokenSummarizer, finished_call(), StubSummarizer, test_a_dead_summariser_still_produces_a_usable_wrap_up(), test_a_nonsense_urgency_falls_back_rather_than_being_stored(), test_an_escalated_call_is_the_one_marked_urgent(), test_slack_failure_does_not_cost_the_crm_note(), test_the_crm_always_gets_it_even_with_nothing_configured() (+3 more)

### Community 48 - "notify/service.py"
Cohesion: 0.20
Nodes (8): _body(), _brand(), on_booking(), on_call_end(), _recap_lines(), _resolve_settings(), send_booking_confirmation(), _sender()

### Community 49 - "json"
Cohesion: 0.05
Nodes (31): _group(), _notes_line(), _price(), _product_section(), render(), _render(), _sizes_line(), write() (+23 more)

### Community 50 - "settings.tsx"
Cohesion: 0.12
Nodes (24): expo-router@~57.0.19, Chrome(), RootLayout(), Section(), SettingsScreen(), PrimaryButton(), loadApiBase(), ping() (+16 more)

### Community 51 - "NotionMirror"
Cohesion: 0.20
Nodes (8): call_key(), call_title(), lead_key(), meeting_key(), objection_key(), zuno_id(), NotionMirror, _Session

### Community 52 - "Mobile Agora Client"
Cohesion: 0.16
Nodes (5): AgoraCall, aiAudioParams(), CallHandlers, JoinParams, Levels

### Community 54 - "About Page Brand Marks"
Cohesion: 0.12
Nodes (36): AboutPage(), metadata, ApproveDiscountRow(), DashboardPage(), emptyDraft, CaddyMark, DeepgramMark, DockerMark (+28 more)

### Community 56 - "records.py"
Cohesion: 0.12
Nodes (31): heading(), paragraph(), text(), _booking_times(), brand_body(), brand_values(), call_body(), call_summary_body() (+23 more)

### Community 57 - "mobile/package.json"
Cohesion: 0.04
Nodes (68): dependencies, expo@~57.0.20, expo-blur@~57.0.2, expo-build-properties@~57.0.17, expo-constants@~57.0.17, expo-dev-client@~57.0.18, expo-device@~57.0.1, expo-font@~57.0.3 (+60 more)

### Community 59 - "Icon Generation Script"
Cohesion: 0.23
Nodes (8): here, loadMark(), main(), out, render(), repo, square(), write()

### Community 60 - "test_notion_sync.py"
Cohesion: 0.09
Nodes (22): clear(), emit(), _run(), subscribe(), register_all(), register(), bus_snapshot(), _Catalog (+14 more)

### Community 62 - "[id].tsx"
Cohesion: 0.13
Nodes (24): @expo/vector-icons@^15.0.2, Brief(), Header(), RepCallScreen(), Stage, EASING, REACT, Ring() (+16 more)

### Community 63 - "EspoCRM Environment Config"
Cohesion: 0.18
Nodes (13): ESPOCRM_ADMIN_PASSWORD, ESPOCRM_ADMIN_USERNAME, ESPOCRM_CONFIG_USE_WEB_SOCKET, ESPOCRM_CONFIG_WEB_SOCKET_URL, ESPOCRM_CONFIG_WEB_SOCKET_ZERO_M_Q_SUBMISSION_DSN, ESPOCRM_CONFIG_WEB_SOCKET_ZERO_M_Q_SUBSCRIBER_DSN, ESPOCRM_DATABASE_HOST, ESPOCRM_DATABASE_PASSWORD (+5 more)

### Community 64 - "EspoCRM Environment Config"
Cohesion: 0.18
Nodes (13): ESPOCRM_ADMIN_PASSWORD, ESPOCRM_ADMIN_USERNAME, ESPOCRM_CONFIG_USE_WEB_SOCKET, ESPOCRM_CONFIG_WEB_SOCKET_URL, ESPOCRM_CONFIG_WEB_SOCKET_ZERO_M_Q_SUBMISSION_DSN, ESPOCRM_CONFIG_WEB_SOCKET_ZERO_M_Q_SUBSCRIBER_DSN, ESPOCRM_DATABASE_HOST, ESPOCRM_DATABASE_PASSWORD (+5 more)

### Community 65 - "delivery.py"
Cohesion: 0.26
Nodes (7): deliver(), _settings(), to_crm(), to_email(), to_slack(), CallSummary, test_as_text_is_one_account_of_the_call_for_all_three_routes()

### Community 67 - "notion/schema.py"
Cohesion: 0.10
Nodes (20): bullet(), callout(), link_to_database(), link_to_page(), mention(), put(), start_page_blocks(), build_properties() (+12 more)

### Community 68 - "retriever.py"
Cohesion: 0.12
Nodes (18): build_corpus(), Chunk, _chunk_markdown(), _chunk_pricing_json(), load_documents(), get_index(), KeywordIndex, reset_index() (+10 more)

### Community 69 - "ref_react"
Cohesion: 0.27
Nodes (8): react-native-safe-area-context@~5.7.0, EscalationsScreen(), Row(), EscalationRecord, useInboxPoll(), useRepUnlocked(), timeAgo(), react-native-safe-area-context

### Community 70 - "provision.py"
Cohesion: 0.09
Nodes (17): brand_key(), build_seed(), _display(), family_key(), family_names(), mode_for(), note_key(), note_names() (+9 more)

### Community 71 - "json"
Cohesion: 0.15
Nodes (7): _build_prompt(), consult(), heuristic_answer(), LLMSpecialistClient, SpecialistClient, _ask_solutions_engineer(), test_an_unavailable_engineer_refuses_to_invent_an_answer()

### Community 72 - "ProductViewer3D.tsx"
Cohesion: 0.22
Nodes (12): buildModel(), capMaterial(), defaultTint(), glass(), juice(), Label, makeLabel(), ProductViewer3D() (+4 more)

### Community 74 - "Backend Service Compose"
Cohesion: 0.18
Nodes (11): container_name, depends_on, env_file, environment, restart, volumes, espocrm, ESPOCRM_BASE_URL (+3 more)

### Community 75 - "MariaDB Service Config"
Cohesion: 0.20
Nodes (10): MARIADB_DATABASE, MARIADB_PASSWORD, MARIADB_ROOT_PASSWORD, MARIADB_USER, container_name, environment, image, restart (+2 more)

### Community 76 - "Caddy Proxy Config"
Cohesion: 0.18
Nodes (11): container_name, depends_on, environment, image, ports, profiles, restart, volumes (+3 more)

### Community 77 - "MariaDB Service Config"
Cohesion: 0.20
Nodes (10): MARIADB_DATABASE, MARIADB_PASSWORD, MARIADB_ROOT_PASSWORD, MARIADB_USER, container_name, environment, image, restart (+2 more)

### Community 78 - "Brief.tsx"
Cohesion: 0.17
Nodes (14): Brief(), fmt(), List(), MOOD_Y, Stat(), URGENCY, DealCard(), DealConcession (+6 more)

### Community 79 - "pipeline.py"
Cohesion: 0.07
Nodes (25): _build_filler_words(), _build_tts_params(), profile_for(), _zuno_minimax_voice(), _zuno_sarvam_speaker(), from_text(), get_profile(), LanguageProfile (+17 more)

### Community 80 - "EspoCRM Service Compose"
Cohesion: 0.22
Nodes (9): espocrm-db, container_name, condition, depends_on, image, ports, restart, volumes (+1 more)

### Community 81 - "EspoCRM Service Compose"
Cohesion: 0.22
Nodes (9): espocrm-db, container_name, condition, depends_on, image, ports, restart, volumes (+1 more)

### Community 82 - "test_espo_crm.py"
Cohesion: 0.05
Nodes (27): EspoCalendarStore, _grid(), slot_id_for(), from_espo_datetime(), to_espo_datetime(), _client(), test_availability_marks_slots_taken_by_existing_meetings(), handler() (+19 more)

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

### Community 88 - "test_knowledge_graph.py"
Cohesion: 0.15
Nodes (9): reset(), set_path(), test_facts_are_one_hop_extracted_first_and_skip_code(), test_limit_and_missing_graph(), test_perfume_mode_uses_the_fragrance_specialist(), test_real_apple_graph_answers_with_labelled_lines(), test_stopwords_alone_seed_nothing(), tiny_graph() (+1 more)

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

### Community 94 - "executor.py"
Cohesion: 0.10
Nodes (10): emit(), slot_label(), publish(), _calendar_check_availability(), _crm_qualify_lead(), _dt(), _emit_lead(), _log_objection() (+2 more)

### Community 96 - "Service Healthcheck Config"
Cohesion: 0.33
Nodes (6): healthcheck, interval, retries, start_period, test, timeout

### Community 97 - "Frontend Build Config"
Cohesion: 0.40
Nodes (6): NEXT_PUBLIC_BACKEND_URL, build, args, context, dockerfile, build

### Community 98 - "Service Healthcheck Config"
Cohesion: 0.33
Nodes (6): healthcheck, interval, retries, start_period, test, timeout

### Community 100 - "SessionState"
Cohesion: 0.09
Nodes (23): NegotiationState, coerce_mode(), default_mode(), detect_requested_mode(), _normalise(), from_utterance(), _retag_lead(), switch_mode() (+15 more)

### Community 102 - "catalogs/catalog.py"
Cohesion: 0.06
Nodes (31): _build(), _Catalog, currency_of(), find(), get(), _index_text(), _load(), match_alias() (+23 more)

### Community 105 - "test_perfume_mode.py"
Cohesion: 0.08
Nodes (33): dispatch(), test_a_desk_that_cannot_answer_falls_back_rather_than_failing_the_turn(), test_nothing_is_priced_before_a_device_count_exists(), test_booking_records_the_slot_id_for_the_call_end_hook(), _payload(), perfume_session(), test_a_company_on_record_counts_as_corporate(), test_an_individual_never_gets_a_percentage() (+25 more)

### Community 106 - "test_mode_endpoints.py"
Cohesion: 0.09
Nodes (7): agora(), FakeAgora, test_browser_like_user_agent_is_sent(), test_console_mode_toggle(), test_console_mode_toggle_errors(), test_product_image_fetch_failure_is_a_502(), test_product_image_is_fetched_once_then_cached()

### Community 110 - ".mcp.json"
Cohesion: 0.50
Nodes (3): graphify-mcp, agora-docs, graphify

### Community 119 - "savings.py"
Cohesion: 0.21
Nodes (6): admin_minutes(), agent_minutes(), total_minutes(), test_an_escalation_saves_no_human_time(), test_repeated_data_entry_is_counted_once_but_lookups_are_not(), test_talk_time_and_paperwork_are_reported_apart()

### Community 120 - "SessionState"
Cohesion: 0.11
Nodes (20): TranscriptTurn, switch_note(), _build_system_prompt(), _history_to_anthropic_messages(), _render_boutique_negotiation(), _render_call_state(), _render_negotiation(), _render_spotlight() (+12 more)

### Community 121 - "json"
Cohesion: 0.20
Nodes (4): _now(), load_state(), save_state(), _state_dir()

### Community 122 - "perfume_support.py"
Cohesion: 0.13
Nodes (12): set_path(), bus_events(), BusRecorder, perfume_catalog(), _id(), test_aliases_match_on_word_boundaries_only(), test_apostrophes_and_accents_do_not_stop_a_match(), test_each_mode_matches_only_its_own_catalog() (+4 more)

### Community 123 - "HandoffCard.tsx"
Cohesion: 0.24
Nodes (9): Escalation, EscalationBrief, Guard(), HandoffCard(), JoinLink(), SignalsCard(), RightBrain, CheckIcon() (+1 more)

### Community 127 - "tools_for"
Cohesion: 0.40
Nodes (3): _perfume_tools(), tools_for(), test_perfume_tools_are_described_for_the_boutique()

### Community 136 - "escalate"
Cohesion: 0.15
Nodes (5): Inbox, escalate(), _FakeLLMClient, test_escalate_service_end_to_end_with_fake_llm_and_no_webhook(), test_escalate_service_falls_back_to_heuristic_on_bad_llm_output()

### Community 137 - "handoff.py"
Cohesion: 0.15
Nodes (9): _body(), send_join_link(), _subject(), build_message(), send(), _escalation_record(), test_handoff_body_omits_company_line_when_absent(), test_handoff_subject_omits_devices_for_a_person_with_no_company() (+1 more)

## Knowledge Gaps
- **2 isolated node(s):** `graphify-mcp`, `expo/tsconfig.base`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 994 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **31 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_settings()` connect `get_settings` to `sessions/models.py`, `Settings`, `controller.py`, `Voice Direction Layer`, `Handoff and Admin Service`, `Memory Client Session`, `handoff.py`, `CalendarStore`, `Espo Lead Store`, `handoff/service.py`, `publisher.py`, `test_inventory.py`, `Task Management Service`, `llm_client.py`, `Bridge Line Orchestration`, `notify/service.py`, `delivery.py`, `pipeline.py`, `executor.py`, `SessionState`, `SessionState`, `json`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Are the 34 inferred relationships involving `SessionState` (e.g. with `_agreed()` and `build()`) actually correct?**
  _`SessionState` has 34 INFERRED edges - model-reasoned connections that need verification._
- **What connects `graphify-mcp`, `expo/tsconfig.base` to the rest of the system?**
  _2 weakly-connected nodes found - possible missing edges._
- **Should `FakeNotion` be split into smaller, more focused modules?**
  _Cohesion score 0.05112279025322503 - nodes in this community are weakly interconnected._
- **Why does `SessionState` connect `SessionState` to `sessions/models.py`, `get_settings`, `controller.py`, `Voice Direction Layer`, `Escalation Specialist Layer`, `handoff/service.py`, `Deal Negotiation Models`, `build`, `publisher.py`, `test_inventory.py`, `test_capacity.py`, `test_notify.py`, `RightBrain`, `test_handoff_summary.py`, `notify/service.py`, `json`, `pipeline.py`, `test_knowledge_graph.py`, `SessionState`, `catalogs/catalog.py`, `test_perfume_mode.py`, `test_mode_endpoints.py`, `perfume_support.py`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `Settings` (e.g. with `_build_asr_params()` and `_build_filler_words()`) actually correct?**
  _`Settings` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Should `Settings` be split into smaller, more focused modules?**
  _Cohesion score 0.08943089430894309 - nodes in this community are weakly interconnected._