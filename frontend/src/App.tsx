import { useCallback, useEffect, useRef, useState } from "react";

import { conversationId, requestLocation, sendMessage } from "./lib/rasa";
import type { ChatMessage, CustomPayload, RasaButton } from "./lib/types";
import { CustomCard } from "./components/Cards";
import { AgentIcon, LeafIcon, LocationIcon, MicIcon, SendIcon } from "./components/Icons";

/** Rich text from the bot is plain text plus **bold**; anything else is escaped
 *  by React automatically. Deliberately not a Markdown library: a chat surface
 *  that renders arbitrary HTML from a model is an injection waiting to happen.
 */
function RichText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((part, index) =>
        part.startsWith("**") && part.endsWith("**") ? (
          <strong key={index}>{part.slice(2, -2)}</strong>
        ) : (
          <span key={index}>{part}</span>
        ),
      )}
    </>
  );
}

const uid = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

/** Payloads that ask the browser for something before the message is sent. */
const LOCATION_PAYLOAD = "/share_location";

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [handoverRef, setHandoverRef] = useState<string | null>(null);
  const [latency, setLatency] = useState<number | null>(null);
  const [listening, setListening] = useState(false);

  const sender = useRef(conversationId());
  const transcriptRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const greetedRef = useRef(false);

  /* ------------------------------------------------------------------ */
  /* Sending                                                             */
  /* ------------------------------------------------------------------ */
  const dispatch = useCallback(
    async (text: string, display?: string | null, metadata?: Record<string, unknown>) => {
      if (!text.trim() || busy) return;

      // `display: null` sends the message without showing a user bubble, which
      // is how the opening greeting works — the traveller never typed it.
      if (display !== null) {
        const shown = display ?? text;
        setMessages((prev) => [...prev, { id: uid(), author: "user", text: shown, at: Date.now() }]);
      }
      setBusy(true);
      setDraft("");

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const result = await sendMessage({
        sender: sender.current,
        message: text,
        metadata,
        signal: controller.signal,
      });

      // A newer dispatch has taken over: it owns `busy` and the transcript now,
      // so this one must write nothing. Without this guard a superseded reply
      // clears `busy` while the newer request is still in flight.
      if (abortRef.current !== controller) return;

      if (!result.ok) {
        // Always clear `busy`, cancellation included. Returning early here left
        // the composer permanently disabled whenever a request was aborted.
        setBusy(false);
        if (result.error === "cancelled") return;
        setMessages((prev) => [
          ...prev,
          { id: uid(), author: "bot", text: result.error, at: Date.now(), failed: true },
        ]);
        return;
      }

      setLatency(result.latencyMs);

      const incoming: ChatMessage[] = result.responses.flatMap((response) => {
        const turns: ChatMessage[] = [];
        if (response.text || response.buttons) {
          turns.push({
            id: uid(),
            author: "bot",
            text: response.text,
            buttons: response.buttons,
            at: Date.now(),
          });
        }
        if (response.custom) {
          turns.push({ id: uid(), author: "bot", custom: response.custom, at: Date.now() });
          if (response.custom.type === "handover") setHandoverRef(response.custom.reference);
        }
        return turns;
      });

      setMessages((prev) => [...prev, ...incoming]);
      setBusy(false);
    },
    [busy],
  );

  /** A quick reply may need browser permission before it can be answered. */
  const onQuickReply = useCallback(
    async (button: RasaButton) => {
      if (button.payload === LOCATION_PAYLOAD) {
        const coords = await requestLocation();
        if (!coords) {
          setMessages((prev) => [
            ...prev,
            {
              id: uid(),
              author: "bot",
              text: "I couldn't get your location — your browser blocked it, which is a perfectly reasonable choice. Just type the city you're starting from instead.",
              at: Date.now(),
            },
          ]);
          composerRef.current?.focus();
          return;
        }
        void dispatch(button.payload, button.title, { location: coords });
        return;
      }
      void dispatch(button.payload, button.title);
    },
    [dispatch],
  );

  /* ------------------------------------------------------------------ */
  /* Lifecycle                                                           */
  /* ------------------------------------------------------------------ */
  useEffect(() => {
    // Open the conversation so the traveller lands on something, not a void.
    // Sent with `display: null`: the greeting is the assistant introducing
    // itself, not the traveller saying hello, so no user bubble is shown.
    // React 18 StrictMode fires this twice in development. Aborting the first
    // request only hid its reply: the server still processed both, and user
    // testing logged two greetings. The ref sends exactly one.
    if (greetedRef.current) return;
    greetedRef.current = true;
    void dispatch("/greet", null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const node = transcriptRef.current;
    if (!node) return;
    node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  // No abort-on-unmount: App is the root and only unmounts with the page, while
  // StrictMode's simulated unmount would abort the single greeting request.

  /* ------------------------------------------------------------------ */
  /* Optional voice input (progressive enhancement)                      */
  /* ------------------------------------------------------------------ */
  const speechSupported =
    typeof window !== "undefined" && ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);

  const toggleVoice = useCallback(() => {
    const Ctor =
      (window as unknown as { SpeechRecognition?: new () => any; webkitSpeechRecognition?: new () => any })
        .SpeechRecognition ??
      (window as unknown as { webkitSpeechRecognition?: new () => any }).webkitSpeechRecognition;
    if (!Ctor) return;

    const recognition = new Ctor();
    recognition.lang = navigator.language || "en-GB";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event: any) => {
      const said = event.results?.[0]?.[0]?.transcript;
      if (said) setDraft((current) => (current ? `${current} ${said}` : said));
      composerRef.current?.focus();
    };
    recognition.onend = () => setListening(false);
    recognition.onerror = () => setListening(false);

    setListening(true);
    recognition.start();
  }, []);

  /* ------------------------------------------------------------------ */
  /* Render                                                              */
  /* ------------------------------------------------------------------ */
  return (
    <div className="app">
      <a className="skip-link" href="#composer">
        Skip to the message box
      </a>

      <header className="app__header">
        <span className="app__mark" aria-hidden="true">
          <LeafIcon size={21} />
        </span>
        <div>
          <h1 className="app__title">Eco-Travel Advisor</h1>
          <p className="app__subtitle">Lower-carbon trip planning · automated assistant</p>
        </div>

        <div className="app__header-actions">
          {latency !== null && (
            <span className="mode-pill" title="Round-trip time of the last reply">
              {latency} ms
            </span>
          )}
          <button
            type="button"
            className="icon-button"
            onClick={() => void dispatch("/request_human_agent", "Talk to a human advisor")}
            disabled={busy}
            aria-label="Request a human travel advisor"
            title="Talk to a human advisor"
          >
            <AgentIcon />
          </button>
        </div>
      </header>

      {handoverRef && (
        <div className="handover-banner" role="status">
          <AgentIcon size={16} />
          <span>
            A human advisor has your conversation. Reference <strong>{handoverRef}</strong>.
          </span>
        </div>
      )}

      <main
        className="transcript"
        ref={transcriptRef}
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
        aria-label="Conversation with the Eco-Travel Advisor"
        tabIndex={0}
      >
        {messages.map((message) => (
          <article key={message.id} className={`turn turn--${message.author}`}>
            <h2 className="visually-hidden">{message.author === "user" ? "You said" : "The advisor replied"}</h2>

            {message.text && (
              <div className={`bubble bubble--${message.failed ? "error" : message.author}`}>
                <RichText text={message.text} />
              </div>
            )}

            {message.custom && (
              <CustomCard payload={message.custom as CustomPayload} />
            )}

            {message.buttons && message.buttons.length > 0 && (
              <div className="quick-replies" role="group" aria-label="Suggested replies">
                {message.buttons.map((button) => (
                  <button
                    key={button.payload + button.title}
                    type="button"
                    className="quick-reply"
                    onClick={() => void onQuickReply(button)}
                    disabled={busy}
                  >
                    {button.payload === LOCATION_PAYLOAD && <LocationIcon size={15} />}
                    {button.title}
                  </button>
                ))}
              </div>
            )}
          </article>
        ))}

        {busy && (
          <div className="turn turn--bot">
            <div className="bubble bubble--bot">
              <span className="typing" aria-hidden="true">
                <span />
                <span />
                <span />
              </span>
              <span className="visually-hidden">The advisor is typing</span>
            </div>
          </div>
        )}
      </main>

      <form
        className="composer"
        id="composer"
        onSubmit={(event) => {
          event.preventDefault();
          void dispatch(draft);
        }}
      >
        <label className="visually-hidden" htmlFor="composer-input">
          Type your message to the Eco-Travel Advisor
        </label>
        <textarea
          id="composer-input"
          ref={composerRef}
          className="composer__input"
          rows={1}
          value={draft}
          placeholder="Where would you like to go?"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void dispatch(draft);
            }
          }}
          disabled={busy}
        />

        {speechSupported && (
          <button
            type="button"
            className="icon-button"
            onClick={toggleVoice}
            aria-pressed={listening}
            aria-label={listening ? "Stop voice input" : "Start voice input"}
            title="Dictate a message"
          >
            <MicIcon />
          </button>
        )}

        <button type="submit" className="composer__send" disabled={busy || !draft.trim()} aria-label="Send message">
          <SendIcon />
        </button>
      </form>
    </div>
  );
}
