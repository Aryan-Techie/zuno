"""Tool schemas in Anthropic's `tools` format (input_schema = JSON Schema).

These are executed entirely inside our own backend (see executor.py) rather
than delegated to Agora's `llm.mcp_servers` — see the plan's tradeoff note:
tool execution must also mutate session/CRM state and emit RTM events, so
keeping the whole loop in one process is simpler to build and debug.
"""

TOOLS: list[dict] = [
    {
        "name": "search_pricing_rag",
        "description": (
            "Search Zuno's product, pricing, feature, and competitor-comparison "
            "knowledge base. Always use this instead of guessing at prices, "
            "features, or competitor comparisons."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The customer's question, in natural language."},
                "top_k": {"type": "integer", "description": "Number of results to return.", "default": 4},
            },
            "required": ["query"],
        },
    },
    {
        "name": "check_inventory",
        "description": (
            "Check LIVE stock for a product: how many units are on hand right "
            "now, the lead time if they are not, and the unit price. Use this "
            "for anything about availability, quantities, or delivery - 'do you "
            "have', 'how many', 'is it in stock', 'can we get 200 by October'. "
            "search_pricing_rag does NOT know stock: it reads fixed documents, "
            "while this reads the warehouse record that changes during the day. "
            "Never state or estimate availability without calling this first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product": {
                    "type": "string",
                    "description": (
                        "The product as the customer named it, e.g. 'iPhone 15', "
                        "'MacBook Airs', 'the 11 inch iPad Pro'. Do not translate "
                        "it into a SKU."
                    ),
                },
                "quantity": {
                    "type": "integer",
                    "description": "How many they asked for, if they named a number.",
                },
            },
            "required": ["product"],
        },
    },
    {
        "name": "crm_upsert_lead",
        "description": (
            "Create or update the qualification record for this call. Only pass "
            "fields the customer actually stated or changed — omitted fields are "
            "left untouched, so this is safe to call repeatedly as new details "
            "come up (including corrections, e.g. user count changing). Capture "
            "WHO you are speaking to as well as what they need: a caller who "
            "opens with 'this is Priya from Northwind Logistics' has just given "
            "you both name and company, and a record without them is of no use "
            "to the rep who picks this lead up afterwards."
        ),
        "input_schema": {
            "type": "object",
            # Every property carries its own description. Without them the
            # model reliably filled in the numeric qualification fields and
            # left name/company empty, even when the caller had stated both in
            # their opening sentence - confirmed twice on scripted runs.
            "properties": {
                "company": {
                    "type": "string",
                    "description": "The customer's company/organisation name, e.g. 'Northwind Logistics'.",
                },
                "user_count": {
                    "type": "integer",
                    "description": "How many devices or employees the deployment covers.",
                },
                "budget_range": {
                    "type": "string",
                    "description": "Budget as stated, e.g. 'around 60 thousand'.",
                },
                "timeline": {
                    "type": "string",
                    "description": "When they need the devices, e.g. 'end of October'.",
                },
                "pain_points": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "What is driving the change, in their words.",
                },
                "decision_stage": {
                    "type": "string",
                    "enum": ["discovery", "evaluating", "ready_to_buy", "not_a_fit"],
                    "description": "How close they are to a decision, on your read of the call.",
                },
                "name": {
                    "type": "string",
                    "description": "The name of the person on the call, e.g. 'Priya'.",
                },
                "title": {
                    "type": "string",
                    "description": "Their job title or role, e.g. 'IT Director' — how much weight their decision carries.",
                },
                "industry": {
                    "type": "string",
                    "description": "The customer's industry/vertical, e.g. 'Logistics' or 'Healthcare', if it comes up naturally.",
                },
                "email": {"type": "string", "description": "Their email address, if given."},
                "phone": {
                    "type": "string",
                    "description": "Their phone number - a backup contact if email bounces or the line drops.",
                },
            },
        },
    },
    {
        "name": "crm_qualify_lead",
        "description": "Mark the lead for this call as qualified or disqualified, with a short reason.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["qualified", "disqualified"]},
                "reason": {"type": "string"},
            },
            "required": ["status", "reason"],
        },
    },
    {
        "name": "calendar_check_availability",
        "description": "Check available meeting slots, optionally within a date range (ISO 8601 datetimes).",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_range_start": {"type": "string", "description": "ISO 8601 datetime, optional."},
                "date_range_end": {"type": "string", "description": "ISO 8601 datetime, optional."},
            },
        },
    },
    {
        "name": "calendar_book_meeting",
        "description": "Book a specific meeting slot by its slot_id (from calendar_check_availability).",
        "input_schema": {
            "type": "object",
            "properties": {"slot_id": {"type": "string"}},
            "required": ["slot_id"],
        },
    },
    {
        "name": "calendar_reschedule_meeting",
        "description": (
            "Move the meeting already booked on this call to a different slot_id "
            "(from calendar_check_availability). Cancels the old time and books the "
            "new one in a single step - never tell the customer it's moved without "
            "calling this."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"new_slot_id": {"type": "string"}},
            "required": ["new_slot_id"],
        },
    },
    {
        "name": "calendar_cancel_meeting",
        "description": (
            "Cancel the meeting already booked on this call. Use when the customer "
            "explicitly wants to call it off rather than move it - for moving to a "
            "new time, use calendar_reschedule_meeting instead."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "schedule_followup",
        "description": (
            "Log a follow-up task for the rep for something that isn't a meeting - "
            "'call back after they've talked to their CFO', 'send the case study "
            "Thursday', 'check in once they've evaluated internally'. Use this "
            "instead of just saying you'll make a note, so it actually lands "
            "somewhere a rep will see it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "note": {"type": "string", "description": "What the rep needs to do, in one sentence."},
                "due": {
                    "type": "string",
                    "description": "When, if they gave a timeframe, e.g. 'next Thursday' or 'in two weeks'. Optional.",
                },
            },
            "required": ["note"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Hand this call off to a human specialist with full context. Use when "
            "the customer explicitly asks for a person, or you genuinely can't "
            "resolve something after real effort."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
    },
    {
        "name": "log_objection",
        "description": (
            "Record a pricing, trust, or product objection the customer raised. "
            "Call again with resolved=true once you've addressed it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "enum": ["pricing", "trust", "product"]},
                "raised_text": {"type": "string", "description": "What the customer said, briefly."},
                "resolved": {"type": "boolean", "default": False},
                "resolution_text": {"type": "string"},
            },
            "required": ["topic", "raised_text"],
        },
    },
    {
        "name": "ask_solutions_engineer",
        "description": (
            "Put a technical question to a deployment engineer - compatibility, "
            "migration, MDM, security, integration, rollout. Use whenever "
            "search_pricing_rag does not settle one, instead of escalating and "
            "instead of guessing. Not for pricing - that is negotiate_deal."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The technical question, in the customer's own terms.",
                },
                "their_setup": {
                    "type": "string",
                    "description": "Their current environment - software, fleet, IT tooling.",
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "negotiate_deal",
        "description": (
            "What you are allowed to offer when the customer pushes on price: a "
            "discount request, a target number, a competing quote, or 'what's your "
            "best price'. Consults the deal desk and returns a priced, authorised "
            "offer. Required before putting ANY discount, target price or trade-in "
            "figure to a customer. Call it again each time they push again."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_ask": {
                    "type": "string",
                    "description": "What they asked for, in their own words.",
                },
                "requested_discount_pct": {
                    "type": "number",
                    "description": "Only if they named a percentage, e.g. 15.",
                },
                "target_total_price": {
                    "type": "number",
                    "description": "Only if they named a total to hit, e.g. 90000.",
                },
                "target_unit_price": {
                    "type": "number",
                    "description": "Only if they named a per-device price, e.g. 850.",
                },
                "competitor_quote": {
                    "type": "string",
                    "description": "The competing quote, if any.",
                },
                "device_mix": {
                    "type": "array",
"description": "Only when they named models. Omitted, all MacBook Airs.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "model": {"type": "string"},
                            "quantity": {"type": "integer"},
                        },
                        "required": ["model", "quantity"],
                    },
                },
                "trade_in_devices": {
                    "type": "integer",
                    "description": "Devices they would trade in, if stated.",
                },
                "financing": {
                    "type": "boolean",
                    "description": "True if the blocker is cash flow, not total cost.",
                },
            },
            "required": ["customer_ask"],
        },
    },
    {
        "name": "update_sentiment",
        "description": "Record a noticeable shift in the customer's tone.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sentiment": {
                    "type": "string",
                    "enum": ["positive", "neutral", "skeptical", "frustrated"],
                }
            },
            "required": ["sentiment"],
        },
    },
]

# Both modes. Placed last so the Apple schemas above stay byte-identical to
# what scripts/bench_llm.py measured tool selection against.
SHOW_PRODUCT_TOOL: dict = {
    "name": "show_product",
    "description": (
        "Put one product on the customer's screen while you talk about it. Call it when a "
        "specific product becomes the subject - one you are recommending or one they asked "
        "about - in the SAME step as any other tool you are calling; never spend a step on it "
        "alone, because the screen also follows the product names said on the call. Returns "
        "the catalog's own facts about the product (sizes, prices, notes), which are the only "
        "facts about it you may state."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "product": {
                "type": "string",
                "description": "The product's name as the catalog has it, e.g. 'Sauvage Eau de Parfum' or 'MacBook Air (M5)'.",
            }
        },
        "required": ["product"],
    },
}

TOOLS.append(SHOW_PRODUCT_TOOL)


# Perfume mode re-describes the tools the boutique uses differently. Same
# names and the same handlers - only what the model is told they are for
# changes, so a tool chosen in one persona cannot leak the other's framing
# ("deployment engineer", "devices") into the conversation.
_PERFUME_DESCRIPTIONS: dict[str, str] = {
    "search_pricing_rag": (
        "Search the boutique's knowledge base: every Dior fragrance, makeup and skincare product "
        "we carry (olfactory family, notes, concentration, sizes and HK$ prices) and the "
        "boutique's own policies (samples, engraving, gift wrap, delivery across Hong Kong, "
        "returns, consultations). Always use this before recommending or pricing anything - "
        "never describe a product, a note or a price from memory."
    ),
    "check_inventory": (
        "Check how many units of a product the boutique has on hand right now. Use it for "
        "anything about availability - 'do you have it', 'is the 100 ml in stock', 'can I pick "
        "it up today', 'I need twelve for the office'. search_pricing_rag does NOT know stock. "
        "Never state availability without calling this first."
    ),
    "ask_solutions_engineer": (
        "Put a detailed product question to the boutique's senior fragrance and skincare "
        "specialist - ingredients and allergens, sensitive skin, how a scent wears and how "
        "long it lasts, layering, which concentration or formula suits. Use it whenever "
        "search_pricing_rag does not settle one, instead of guessing and instead of "
        "escalating. Not for prices - those are fixed and in the knowledge base."
    ),
    "negotiate_deal": (
        "Required whenever the customer asks for a discount, a better price, a promo code or a "
        "price match, or names a budget below the price. Boutique prices are fixed: this "
        "returns the complimentary extras you may offer instead and, ONLY for a corporate "
        "gifting order of 10 or more pieces, a small authorised corporate price. Never offer "
        "any discount, percentage or price that did not come from this tool."
    ),
    "calendar_check_availability": (
        "Check open slots for an in-boutique consultation (fragrance, makeup or skincare), "
        "optionally within a date range (ISO 8601 datetimes)."
    ),
    "calendar_book_meeting": "Book an in-boutique consultation slot by its slot_id (from calendar_check_availability).",
}

_PERFUME_PROPERTY_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "crm_upsert_lead": {
        "company": "Their company - ONLY for a corporate gifting order, never for a personal purchase.",
        "user_count": "How many pieces they want, e.g. 2, or 25 for a corporate gifting order.",
        "budget_range": "Budget as stated, in their words, e.g. 'around fifteen hundred Hong Kong dollars'.",
        "timeline": "When they need it, e.g. 'before her birthday on the 12th'.",
        "pain_points": (
            "What they are looking for, in their words: who it is for, the occasion, notes they "
            "love or dislike, how intense they like it."
        ),
        "title": "Only for a corporate gifting order: their role.",
        "industry": "Only for a corporate gifting order: the company's industry.",
    },
    "negotiate_deal": {
        "device_mix": (
            "The products and quantities, e.g. [{'model': 'Sauvage Eau de Parfum 100 ml', "
            "'quantity': 20}]. Omitted, the product on screen is used."
        ),
        "trade_in_devices": "Not used at the boutique - leave it out.",
        "financing": "Not used at the boutique - leave it out.",
        "target_unit_price": "Only if they named a price per piece, in HK$.",
        "target_total_price": "Only if they named a total, in HK$.",
    },
    "check_inventory": {
        "product": (
            "The product as the customer named it, e.g. 'Sauvage', 'the Miss Dior 50 ml', "
            "'Rouge Dior 999'."
        ),
        "quantity": "How many they asked for, if they named a number.",
    },
}

_CORPORATE_GIFTING_PROPERTY = {
    "type": "boolean",
    "description": "True only when a company is buying these as gifts (clients, staff, an event).",
}


def _perfume_tools() -> list[dict]:
    import copy

    tools = copy.deepcopy(TOOLS)
    for tool in tools:
        name = tool["name"]
        if name in _PERFUME_DESCRIPTIONS:
            tool["description"] = _PERFUME_DESCRIPTIONS[name]
        properties = tool["input_schema"].get("properties", {})
        for prop, description in _PERFUME_PROPERTY_DESCRIPTIONS.get(name, {}).items():
            if prop in properties:
                properties[prop]["description"] = description
        if name == "negotiate_deal":
            properties["corporate_gifting"] = dict(_CORPORATE_GIFTING_PROPERTY)
    return tools


_TOOLS_BY_MODE: dict[str, list[dict]] = {"apple": TOOLS}


def tools_for(mode: str) -> list[dict]:
    """The tool schemas the model sees in `mode`. Built once per mode."""
    if mode not in _TOOLS_BY_MODE:
        _TOOLS_BY_MODE[mode] = _perfume_tools() if mode == "perfume" else TOOLS
    return _TOOLS_BY_MODE[mode]
