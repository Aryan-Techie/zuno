import type { Metadata } from "next";
import { Logo } from "@/components/Logo";
import { NavLinks } from "@/components/NavLinks";
import { StoryOrb } from "@/components/StoryOrb";
import {
  GeminiMark,
  DeepgramMark,
  MiniMaxMark,
  NextJsMark,
  FastApiMark,
  OracleMark,
  CaddyMark,
  ExpoMark,
} from "@/components/BrandMarks";
import {
  DoodleUnderline,
  DoodleArrow,
  DoodleSpark,
  DoodleCircle,
  DoodleWave,
  DoodleCheck,
  DoodleDivider,
  DoodleLoop,
} from "@/components/Doodles";

export const metadata: Metadata = {
  title: "Zuno — the voice agent that keeps the thread",
  description:
    "A real-time voice sales agent built human-in-the-loop: Zuno holds the call, answers from a grounded knowledge base and writes the CRM; a human decides money and exceptions.",
};

const AGORA_LOGO = "/agora-logo.png";
const ESPOCRM_LOGO = "/espocrm-logo.svg";

export default function AboutPage() {
  return (
    <div className="app story-page">
      <header className="top">
        <div className="brand">
          <Logo size={24} />
          <span>Zuno</span>
          <span className="sub">Story</span>
        </div>
        <div className="actions">
          <NavLinks current="/about" />
        </div>
      </header>

      <main>
        {/* ---------- hero ---------- */}
        <section className="story-hero">
          <div className="story-orb-wrap">
            <StoryOrb />
          </div>
          <div className="story-badge">
            <span>Powered by</span>
            <img src={AGORA_LOGO} alt="Agora" />
          </div>
          <h1 className="headline">The AI holds the call. A person makes the call.</h1>
          <DoodleUnderline className="doodle" style={{ margin: "-6px auto 0", display: "block" }} />
          <p className="story-sub">
            Zuno is a real-time voice sales agent. It talks to the caller, answers from a knowledge
            base it can point to, and fills in the CRM while the caller is still speaking. Discounts,
            exceptions and anything it isn&apos;t sure of go to a human, with the context already
            written up.
          </p>
          <div className="story-cta-row">
            <a href="/" className="primary">
              Talk to Zuno
            </a>
            <a href="#journey" className="ghost">
              Follow one call
            </a>
          </div>
        </section>

        {/* ---------- the problem ---------- */}
        <section className="story-section">
          <div className="story-section-head">
            <p className="story-eyebrow">
              The problem <DoodleSpark className="doodle faint" size={13} style={{ verticalAlign: "middle" }} />
            </p>
            <h2>Scripted bots break. Zuno keeps the thread.</h2>
            <p>
              A scripted voice bot works until the caller interrupts, changes a number they already
              gave, or asks things out of order. Then it restarts the flow or hands off with nothing
              attached. Zuno decides each turn from what has been said so far, so a correction
              updates the record instead of starting over.
            </p>
          </div>
          <div className="story-grid">
            <div className="card">
              <h3>Interruptions stop it</h3>
              <p>
                Talk over Zuno and it stops speaking. Barge-in and turn-taking come from Agora&apos;s
                Conversational AI Engine, inside the call itself.
              </p>
            </div>
            <div className="card">
              <h3>Corrections overwrite</h3>
              <p>
                &ldquo;Actually, make it 50, not 25.&rdquo; The same lead record gets one field
                changed. No second lead, no repeated questions.
              </p>
            </div>
            <div className="card">
              <h3>Any order works</h3>
              <p>
                There is no flow chart. A tool loop picks the next step each turn: search the
                catalog, update the lead, book a meeting, negotiate, or hand off.
              </p>
            </div>
          </div>
        </section>

        {/* ---------- HITL ---------- */}
        <section className="story-section" id="hitl">
          <div className="story-section-head">
            <p className="story-eyebrow">Human in the loop</p>
            <h2>
              Who decides what.{" "}
              <DoodleCircle className="doodle faint" size={20} style={{ verticalAlign: "middle" }} />
            </h2>
            <p>
              The split is fixed in code, not left to the model&apos;s judgement on the day.
            </p>
          </div>
          <div className="story-grid">
            <div className="card">
              <h3>
                Zuno decides{" "}
                <DoodleCheck className="doodle" size={14} style={{ verticalAlign: "middle" }} />
              </h3>
              <p>
                Answers that are stated in our documents, qualification questions, CRM updates,
                meeting bookings and follow-ups, and a discount of up to 3%.
              </p>
            </div>
            <div className="card">
              <h3>The deal desk decides</h3>
              <p>
                A separate deal-desk agent can go to 10%, and only against a commitment such as
                volume or term. An 18% floor is enforced in code: any higher recommendation is
                clamped and the clamp is logged to the CRM.
              </p>
            </div>
            <div className="card">
              <h3>
                A human decides{" "}
                <DoodleCheck className="doodle warm" size={14} style={{ verticalAlign: "middle" }} />
              </h3>
              <p>
                Anything beyond that, plus exceptions and open questions. The rep approves or
                declines from the dashboard inbox or the Expo rep app while the call stays open.
              </p>
            </div>
          </div>
          <p className="story-callout">
            Guardrails force a <strong>warm transfer</strong> when the caller is frustrated more than
            once, when the same objection comes up three times without being resolved, or when Zuno
            would have to answer with low confidence. The human picks up with a written brief: who
            is calling, what they want, what was offered, and what is blocking.
          </p>
        </section>

        {/* ---------- a call's journey ---------- */}
        <section className="story-section" id="journey">
          <div className="story-section-head">
            <p className="story-eyebrow">
              A call&apos;s journey <DoodleWave className="doodle faint" width={22} style={{ verticalAlign: "middle" }} />
            </p>
            <h2>One call, start to finish.</h2>
            <p>What happens on a typical fleet enquiry, in order.</p>
          </div>

          <div className="story-flow">
            <p className="story-flow-label">1. The caller speaks</p>
            <div className="story-flow-row">
              <span className="story-flow-node">🎙️ Caller</span>
              <span className="story-flow-arrow">⇄</span>
              <span className="story-flow-node">
                <img src={AGORA_LOGO} alt="" /> Agora audio
              </span>
              <span className="story-flow-arrow">→</span>
              <span className="story-flow-node">
                <DeepgramMark size={13} /> Deepgram transcript
              </span>
            </div>

            <div className="story-flow-connector">↓</div>

            <p className="story-flow-label">2. Zuno decides the turn</p>
            <div className="story-flow-row">
              <span className="story-flow-node">
                <FastApiMark size={13} /> Tool loop
              </span>
              <span className="story-flow-arrow">⇉</span>
              <span className="story-flow-node">Knowledge graph</span>
              <span className="story-flow-node">
                <img src={ESPOCRM_LOGO} alt="" /> CRM write
              </span>
              <span className="story-flow-node">Product spotlight</span>
              <span className="story-flow-node">Calendar</span>
            </div>

            <div className="story-flow-connector">↓</div>

            <p className="story-flow-label">3. Money or doubt goes to a person</p>
            <div className="story-flow-row">
              <span className="story-flow-node">Deal desk</span>
              <span className="story-flow-arrow">→</span>
              <span className="story-flow-node">Dashboard inbox</span>
              <span className="story-flow-node">
                <ExpoMark size={13} /> Rep app
              </span>
            </div>

            <div className="story-flow-connector">↓</div>

            <p className="story-flow-label">4. Zuno answers</p>
            <div className="story-flow-row">
              <span className="story-flow-node">
                <MiniMaxMark size={13} /> MiniMax voice
              </span>
              <span className="story-flow-arrow">→</span>
              <span className="story-flow-node">🔊 Caller</span>
            </div>
          </div>

          <div className="list agreed" style={{ maxWidth: 680, margin: "28px auto 0" }}>
            <ul>
              <li>
                <DoodleCheck className="doodle" size={13} style={{ verticalAlign: "middle", marginRight: 4 }} />
                The caller names a MacBook Pro. It appears on screen as a 3D model while Zuno
                describes it.
              </li>
              <li>
                <DoodleCheck className="doodle warm" size={13} style={{ verticalAlign: "middle", marginRight: 4 }} />
                Company, headcount and budget land in EspoCRM as they are said. The console shows
                the lead card filling in.
              </li>
              <li>
                The caller asks for 12% off 40 laptops. Zuno can give 3%, so it asks the deal desk,
                which offers 10% against a two-year commitment. The rest goes to the inbox.
              </li>
              <li>
                A rep approves from their phone. Zuno confirms the terms, books a follow-up, and the
                meeting and invite are written to the CRM.
              </li>
            </ul>
          </div>
        </section>

        {/* ---------- two modes ---------- */}
        <section className="story-section" id="modes">
          <div className="story-section-head">
            <p className="story-eyebrow">
              Two modes <DoodleLoop className="doodle faint" size={18} style={{ verticalAlign: "middle" }} />
            </p>
            <h2>Same agent, two shops.</h2>
            <p>
              Each mode has its own catalog, knowledge graph, voice, discount rules and console
              theme. The caller can switch mid-call by saying &ldquo;Dior mode&rdquo;, or the operator
              can use the console toggle.
            </p>
          </div>
          <div className="story-grid">
            <div className="card">
              <h3>Apple devices</h3>
              <p>
                The default. Sells to businesses buying fleets and to individuals buying one device.
                For a solo buyer Zuno skips company and headcount questions. Financing, AppleCare+
                and trade-in work the same either way. Discounts follow the 3% / 10% / 18% ladder
                above.
              </p>
            </div>
            <div className="card" data-mode="perfume">
              <h3>Dior beauty</h3>
              <p>
                A boutique advisor for fragrance, makeup and skincare, from a 78-product catalog
                priced in HK$. Individuals get 0% off and complimentary extras such as samples or
                engraving. Corporate gifting orders of 10 or more can reach 5%.
              </p>
            </div>
          </div>
          <p className="story-note">
            In both modes, a named product is shown on screen with a 3D model, so the caller and the
            operator are looking at the same thing.
          </p>
        </section>

        {/* ---------- graphify ---------- */}
        <section className="story-section" id="graphify">
          <div className="story-section-head">
            <p className="story-eyebrow">
              Knowledge layer <DoodleSpark className="doodle warm" size={13} style={{ verticalAlign: "middle" }} />
            </p>
            <h2>Graphify, used three ways.</h2>
            <p>One tool for what Zuno knows, what the team knows, and how the code fits together.</p>
          </div>
          <div className="story-grid">
            <div className="card">
              <h3>Product knowledge graphs</h3>
              <p>
                One graph per mode, built from our product documents. Each fact is tagged.{" "}
                <code>EXTRACTED</code> means it is stated in our docs, so Zuno can promise it.{" "}
                <code>INFERRED</code> means Graphify resolved it, so it goes to a human as an open
                question instead of being said as fact.
              </p>
            </div>
            <div className="card">
              <h3>The CRM, mirrored to Notion</h3>
              <p>
                Leads, meetings, offers, escalations and the rest are mirrored into 9 linked Notion
                databases. getgraphify.com draws them as the team&apos;s knowledge graph, so a rep can
                see how a deal connects to people, products and past calls.
              </p>
            </div>
            <div className="card">
              <h3>A map of the codebase</h3>
              <p>
                The repository itself is a Graphify graph. Coding agents query it through hooks and
                an MCP server before reading source, so changes start from how the system is
                actually wired.
              </p>
            </div>
          </div>
          <p className="story-callout">
            The rule behind all three: Zuno only commits to what is written down. Anything it had to
            work out becomes a question for a person, not a promise to the caller.
          </p>
        </section>

        {/* ---------- stack ---------- */}
        <section className="story-section" id="stack">
          <div className="story-section-head">
            <p className="story-eyebrow">Stack</p>
            <h2>
              What it runs on.{" "}
              <DoodleCircle className="doodle faint" size={20} style={{ verticalAlign: "middle" }} />
            </h2>
            <p>Every piece below is in the live deployment.</p>
          </div>
          <div className="story-pill-row" style={{ maxWidth: 720 }}>
            <span className="pill info">
              <img src={AGORA_LOGO} alt="" height={13} /> Agora Conversational AI
            </span>
            <span className="pill info">
              <DeepgramMark size={14} /> Deepgram
            </span>
            <span className="pill info">
              <MiniMaxMark size={14} /> MiniMax voices
            </span>
            <span className="pill info">
              <GeminiMark size={14} /> Gemini / Groq / Claude
            </span>
            <span className="pill info">
              <FastApiMark size={14} /> FastAPI
            </span>
            <span className="pill info">
              <NextJsMark size={14} /> Next.js + three.js
            </span>
            <span className="pill info">
              <ExpoMark size={14} /> Expo
            </span>
            <span className="pill info">
              <img src={ESPOCRM_LOGO} alt="" height={13} />
              EspoCRM
            </span>
            <span className="pill info">Notion</span>
            <span className="pill info">Graphify</span>
            <span className="pill info">
              <OracleMark size={14} /> Oracle Cloud
            </span>
            <span className="pill info">
              <CaddyMark size={14} /> Caddy
            </span>
          </div>
          <div className="story-grid" style={{ marginTop: 28 }}>
            <div className="card">
              <h3>Voice</h3>
              <p>
                Agora carries the audio and handles barge-in and turn-taking. Deepgram transcribes,
                MiniMax speaks. Agora calls our backend once per turn.
              </p>
            </div>
            <div className="card">
              <h3>Reasoning</h3>
              <p>
                An LLM tool loop. Gemini, Groq and Claude share one interface; the model for a turn
                is chosen by measured latency on the real prompt and tools, checked for correct tool
                calls.
              </p>
            </div>
            <div className="card">
              <h3>Surfaces</h3>
              <p>
                A Next.js console with three.js product models, a dashboard with the approval inbox,
                and an Expo app for reps. EspoCRM is the system of record.
              </p>
            </div>
          </div>
        </section>

        {/* ---------- faq ---------- */}
        <section className="story-section">
          <div className="story-section-head">
            <p className="story-eyebrow">
              Questions <DoodleSpark className="doodle" size={13} style={{ verticalAlign: "middle" }} />
            </p>
            <h2>Short answers.</h2>
          </div>
          <div className="story-faq">
            <details>
              <summary>What happens when Zuno doesn&apos;t know something?</summary>
              <p>
                It says so. If the answer isn&apos;t stated in the knowledge graph, it is logged as an
                open question for a human, and a low-confidence answer triggers a warm transfer.
              </p>
            </details>
            <details>
              <summary>Can the AI give away a large discount?</summary>
              <p>
                No. Zuno stops at 3%, the deal desk at 10% against a commitment, and the 18% floor is
                a hard limit in code. Anything beyond the AI&apos;s limit needs a person to approve it.
              </p>
            </details>
            <DoodleDivider className="doodle faint" style={{ display: "block", margin: "2px auto" }} />
            <details>
              <summary>Does the human have to listen to the whole call?</summary>
              <p>
                No. The handoff comes with a written brief and the lead record already filled in, so
                the rep can decide from the inbox or join the call already knowing the situation.
              </p>
            </details>
            <details>
              <summary>How does the caller switch to the Dior advisor?</summary>
              <p>
                By saying &ldquo;Dior mode&rdquo; during the call. The catalog, voice, discount
                rules and console theme change together.
              </p>
            </details>
          </div>
        </section>

        {/* ---------- closing ---------- */}
        <section className="story-section" style={{ textAlign: "center" }}>
          <h2 style={{ fontSize: 27, fontWeight: 600, letterSpacing: "-0.02em", margin: "0 0 20px" }}>
            Start a call and watch the record fill in.
          </h2>
          <div className="story-cta-row" style={{ position: "relative" }}>
            <a href="/" className="primary">
              Try the live console
            </a>
            <DoodleArrow
              className="doodle warm"
              style={{ position: "absolute", left: "calc(100% + 4px)", top: "-34px", transform: "scaleX(-1)" }}
            />
          </div>
          <p className="story-fineprint" style={{ marginTop: 18 }}>
            Running on Oracle Cloud behind Caddy with Let&apos;s Encrypt TLS.
          </p>
        </section>
      </main>

      <footer className="story-footer">
        <div className="story-footer-links">
          <a href="/">Talk to Zuno</a>
          <a href="/dashboard">Dashboard</a>
          <a href="/graph">Graph</a>
          <a href="#hitl">Who decides</a>
          <a href="#graphify">Graphify</a>
          <a href="https://github.com/Aryan-Techie/zuno" target="_blank" rel="noreferrer">
            GitHub
          </a>
        </div>
        <div className="story-credit">
          <span>Built on</span>
          <img src={AGORA_LOGO} alt="Agora" />
        </div>
        <p className="story-fineprint">Zuno — for Agora&apos;s Adaptive AI Sales and Negotiation Agent track.</p>
      </footer>
    </div>
  );
}
