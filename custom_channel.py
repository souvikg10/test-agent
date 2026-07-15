# A shareable web chat channel. Rasa's built-in REST channel (always on via
# `rasa run --enable-api`, no credentials.yml needed — this is what the
# local Test panel already talks to) only exposes a bare JSON API, nothing
# a person can open in a browser. This channel reuses RestInput's message
# handling (POST .../webhook) verbatim and adds one thing on top: a GET "/"
# route that serves a minimal, self-contained chat page. Whatever public
# URL Railway assigns this service (see lib/agents/deploy.ts) is then
# directly shareable — no separate widget hosting needed.
#
# Wired up via credentials.yml's `custom_channel.WebChatInput:` entry — Rasa
# resolves an unrecognized credentials.yml key as a "module.ClassName"
# import path (rasa/core/run.py's _create_single_channel), the same
# mechanism this project already relies on for event_broker.py.

import inspect
from typing import Awaitable, Callable, Text, Union

from sanic import Blueprint, response
from sanic.request import Request
from sanic.response import BaseHTTPResponse, HTTPResponse, ResponseStream

from rasa.core.channels.channel import UserMessage
from rasa.core.channels.rest import RestInput

CHAT_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chat</title>
<style>
  :root {
    color-scheme: light dark;
    --accent-1: #7C3AED;
    --accent-2: #5B21B6;
    --accent-3: #C026D3;
    --accent-tint: #F3ECFF;
    --ink: #16151F;
    --ink-soft: #6E6B7C;
    --bg: #F4F2FA;
    --card: #ffffff;
    --border: rgba(22,21,31,.08);
    --bot-bubble: #F5F4F9;
    --positive: #22C55E;
    --user-avatar: #2B2F3A;
    --radius-lg: 22px;
    --shadow-card: 0 1px 1px rgba(30,20,60,.03), 0 30px 60px -20px rgba(40,20,80,.28);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --ink: #EDEBF5; --ink-soft: #9490A6; --bg: #100E17; --card: #1A1723;
      --border: rgba(255,255,255,.08); --bot-bubble: #251F32; --accent-tint: rgba(124,58,237,.18);
      --user-avatar: #4A4E5C;
      --shadow-card: 0 1px 1px rgba(0,0,0,.2), 0 30px 60px -20px rgba(0,0,0,.6);
    }
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
    padding: 24px;
    background:
      radial-gradient(1100px 620px at 12% -12%, color-mix(in srgb, var(--accent-1) 20%, transparent) 0%, transparent 60%),
      radial-gradient(900px 620px at 108% 14%, color-mix(in srgb, var(--accent-3) 16%, transparent) 0%, transparent 55%),
      var(--bg);
    font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  .card {
    width: 100%; max-width: 440px; height: min(680px, 92vh); background: var(--card);
    border: 1px solid var(--border); border-radius: var(--radius-lg); display: flex; flex-direction: column;
    overflow: hidden; box-shadow: var(--shadow-card); position: relative;
    animation: card-in .4s cubic-bezier(.2,.8,.2,1) both;
  }
  @keyframes card-in { from { opacity: 0; transform: translateY(10px) scale(.985); } to { opacity: 1; transform: none; } }
  .card::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px; z-index: 1;
    background: linear-gradient(90deg, var(--accent-1), var(--accent-3));
  }
  @media (max-width: 480px) {
    .card { max-width: 100%; height: 100vh; border-radius: 0; border: none; }
    body { padding: 0; }
  }

  .hd {
    padding: 15px 18px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 11px;
    flex-shrink: 0; background: var(--card);
  }
  .hd-mark {
    width: 36px; height: 36px; border-radius: 11px; flex-shrink: 0;
    background: linear-gradient(135deg, var(--accent-1) 0%, var(--accent-2) 55%, var(--accent-3) 100%);
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 14px -4px color-mix(in srgb, var(--accent-2) 60%, transparent);
  }
  .hd-mark svg { width: 18px; height: 18px; }
  .hd-text { min-width: 0; }
  .hd-title { font-size: 14.5px; font-weight: 650; color: var(--ink); line-height: 1.25; letter-spacing: -.1px; }
  .hd-sub { font-size: 11.5px; color: var(--ink-soft); display: flex; align-items: center; gap: 5px; margin-top: 2px; }
  .hd-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--positive); flex-shrink: 0; box-shadow: 0 0 0 3px color-mix(in srgb, var(--positive) 18%, transparent); }

  .msgs {
    flex: 1; overflow-y: auto; padding: 20px 18px; display: flex; flex-direction: column; gap: 3px;
    scroll-behavior: smooth;
  }
  .msgs::-webkit-scrollbar { width: 6px; }
  .msgs::-webkit-scrollbar-thumb { background: color-mix(in srgb, var(--ink-soft) 35%, transparent); border-radius: 999px; }

  .session-banner {
    align-self: center; font-size: 11px; font-weight: 600; color: var(--accent-2);
    background: var(--accent-tint); padding: 5px 12px; border-radius: 999px; margin-bottom: 14px;
    letter-spacing: .1px;
  }

  .row { display: flex; gap: 8px; max-width: 88%; margin: 3px 0; animation: rise .25s cubic-bezier(.2,.8,.2,1) both; }
  .row.user { align-self: flex-end; flex-direction: row-reverse; }
  .row.bot { align-self: flex-start; }
  @keyframes rise { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

  .avatar-sm {
    width: 24px; height: 24px; border-radius: 50%; flex-shrink: 0; margin-top: 2px;
    display: flex; align-items: center; justify-content: center;
  }
  .avatar-sm svg { width: 13px; height: 13px; }
  .row.bot .avatar-sm { background: linear-gradient(135deg, var(--accent-1), var(--accent-2)); }
  .row.user .avatar-sm { background: var(--user-avatar); }
  .row.user .avatar-sm span { color: #fff; font-size: 10px; font-weight: 700; }

  .bubble-stack { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
  .row.user .bubble-stack { align-items: flex-end; }
  .msg {
    padding: 10px 14px; border-radius: 17px; font-size: 13.5px; line-height: 1.55; white-space: pre-wrap;
    word-break: break-word;
  }
  .row.bot .msg { background: var(--bot-bubble); color: var(--ink); border-bottom-left-radius: 5px; box-shadow: 0 1px 0 rgba(0,0,0,.02); }
  .row.user .msg {
    background: linear-gradient(135deg, var(--accent-1), var(--accent-2)); color: #fff; border-bottom-right-radius: 5px;
    box-shadow: 0 4px 12px -6px color-mix(in srgb, var(--accent-2) 70%, transparent);
  }
  .msg-time { font-size: 10px; color: var(--ink-soft); opacity: .8; padding: 0 4px; }

  .typing-row { align-self: flex-start; display: flex; gap: 8px; margin: 3px 0; }
  .typing-dots {
    background: var(--bot-bubble); border-radius: 17px; border-bottom-left-radius: 5px;
    padding: 13px 14px; display: flex; gap: 4px; align-items: center;
  }
  .typing-dots span {
    width: 6px; height: 6px; border-radius: 50%; background: color-mix(in srgb, var(--ink-soft) 70%, transparent);
    animation: bounce 1.2s infinite ease-in-out;
  }
  .typing-dots span:nth-child(2) { animation-delay: .15s; }
  .typing-dots span:nth-child(3) { animation-delay: .3s; }
  @keyframes bounce { 0%, 60%, 100% { transform: translateY(0); opacity: .5; } 30% { transform: translateY(-4px); opacity: 1; } }

  .buttons { display: flex; flex-wrap: wrap; gap: 6px; align-self: flex-start; max-width: 88%; margin: 2px 0 2px 32px; }
  .btn-chip {
    border: 1px solid color-mix(in srgb, var(--accent-2) 45%, transparent); color: var(--accent-2); background: var(--card);
    border-radius: 999px; padding: 6px 13px; font-size: 12.5px; font-weight: 500; cursor: pointer;
    transition: background .12s ease, transform .1s ease, box-shadow .12s ease;
  }
  .btn-chip:hover { background: var(--accent-tint); transform: translateY(-1px); box-shadow: 0 4px 10px -6px rgba(91,33,182,.35); }
  .btn-chip:active { transform: translateY(0); }

  .empty-state {
    margin: auto; text-align: center; color: var(--ink-soft); font-size: 13px; padding: 0 30px;
  }
  .empty-state .glyph {
    width: 52px; height: 52px; border-radius: 16px; margin: 0 auto 14px; display: flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, var(--accent-1), var(--accent-2));
    box-shadow: 0 8px 20px -8px color-mix(in srgb, var(--accent-2) 60%, transparent);
  }
  .empty-state .glyph svg { width: 24px; height: 24px; }
  .empty-state .eyebrow { font-weight: 600; color: var(--ink); font-size: 13.5px; margin-bottom: 3px; }

  .inp-row {
    display: flex; align-items: flex-end; gap: 8px; padding: 12px 14px; border-top: 1px solid var(--border);
    flex-shrink: 0; background: var(--card);
  }
  .inp {
    flex: 1; border: 1px solid var(--border); border-radius: 15px; padding: 11px 14px; font-size: 13.5px;
    outline: none; font-family: inherit; resize: none; max-height: 120px; line-height: 1.4; color: var(--ink);
    background: color-mix(in srgb, var(--bot-bubble) 60%, transparent); transition: border-color .12s ease, box-shadow .12s ease;
  }
  .inp:focus { border-color: var(--accent-1); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent-1) 15%, transparent); }
  .inp::placeholder { color: var(--ink-soft); }
  .send {
    border: none; background: linear-gradient(135deg, var(--accent-1), var(--accent-2)); color: #fff;
    border-radius: 13px; width: 40px; height: 40px;
    display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0;
    transition: transform .12s ease, box-shadow .12s ease, opacity .12s ease;
    box-shadow: 0 6px 16px -6px color-mix(in srgb, var(--accent-2) 65%, transparent);
  }
  .send:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 8px 20px -6px color-mix(in srgb, var(--accent-2) 75%, transparent); }
  .send:active:not(:disabled) { transform: scale(.94); }
  .send:disabled { opacity: .35; cursor: default; box-shadow: none; }

  @media (prefers-reduced-motion: reduce) {
    .card, .row, .typing-dots span { animation: none !important; }
  }
</style>
</head>
<body>
  <div class="card">
    <div class="hd">
      <div class="hd-mark">
        <svg viewBox="0 0 24 24" fill="none"><path d="M12 2L14.4 9.6L22 12L14.4 14.4L12 22L9.6 14.4L2 12L9.6 9.6L12 2Z" fill="white"/></svg>
      </div>
      <div class="hd-text">
        <div class="hd-title">Assistant</div>
        <div class="hd-sub"><span class="hd-dot"></span>Powered by Rasa Autopilot</div>
      </div>
    </div>
    <div class="msgs" id="msgs">
      <div class="empty-state" id="empty">
        <div class="glyph"><svg viewBox="0 0 24 24" fill="none"><path d="M12 2L14.4 9.6L22 12L14.4 14.4L12 22L9.6 14.4L2 12L9.6 9.6L12 2Z" fill="white"/></svg></div>
        <div class="eyebrow">How can I help?</div>
        Ask a question to get started.
      </div>
    </div>
    <div class="inp-row">
      <textarea class="inp" id="inp" placeholder="Type a message…" rows="1" autocomplete="off"></textarea>
      <button class="send" id="send" aria-label="Send" title="Send">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M14.5 1.5L7.5 8.5M14.5 1.5L10 14.5L7.5 8.5M14.5 1.5L1.5 6L7.5 8.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </button>
    </div>
  </div>
<script>
(function(){
  var sender = localStorage.getItem('rasa_auto_sender');
  if (!sender) { sender = 'web-' + Math.random().toString(36).slice(2, 12); localStorage.setItem('rasa_auto_sender', sender); }
  var msgsEl = document.getElementById('msgs');
  var emptyEl = document.getElementById('empty');
  var inpEl = document.getElementById('inp');
  var sendEl = document.getElementById('send');
  var typingRow = null;
  var BOT_AVATAR_SVG = '<svg viewBox="0 0 24 24" fill="none"><path d="M12 2L14.4 9.6L22 12L14.4 14.4L12 22L9.6 14.4L2 12L9.6 9.6L12 2Z" fill="white"/></svg>';

  function timeLabel() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  function ensureStarted() {
    if (emptyEl) {
      emptyEl.remove();
      emptyEl = null;
      var banner = document.createElement('div');
      banner.className = 'session-banner';
      banner.textContent = 'Session started ' + new Date().toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
      msgsEl.appendChild(banner);
    }
  }
  function addMsg(role, text) {
    ensureStarted();
    var row = document.createElement('div');
    row.className = 'row ' + role;
    var avatar = document.createElement('div');
    avatar.className = 'avatar-sm';
    avatar.innerHTML = role === 'user' ? '<span>Y</span>' : BOT_AVATAR_SVG;
    var stack = document.createElement('div');
    stack.className = 'bubble-stack';
    var bubble = document.createElement('div');
    bubble.className = 'msg';
    bubble.textContent = text;
    var time = document.createElement('div');
    time.className = 'msg-time';
    time.textContent = timeLabel();
    stack.appendChild(bubble);
    stack.appendChild(time);
    row.appendChild(avatar);
    row.appendChild(stack);
    msgsEl.appendChild(row);
    msgsEl.scrollTop = msgsEl.scrollHeight;
  }
  function addButtons(buttons) {
    var wrap = document.createElement('div');
    wrap.className = 'buttons';
    buttons.forEach(function(b) {
      var btn = document.createElement('button');
      btn.className = 'btn-chip';
      btn.textContent = b.title || b.payload || '...';
      btn.onclick = function () { send(b.payload || b.title); };
      wrap.appendChild(btn);
    });
    msgsEl.appendChild(wrap);
    msgsEl.scrollTop = msgsEl.scrollHeight;
  }
  function showTyping() {
    typingRow = document.createElement('div');
    typingRow.className = 'typing-row';
    typingRow.innerHTML = '<div class="avatar-sm" style="background:linear-gradient(135deg,var(--accent-1),var(--accent-2))">' + BOT_AVATAR_SVG + '</div>' +
      '<div class="typing-dots"><span></span><span></span><span></span></div>';
    msgsEl.appendChild(typingRow);
    msgsEl.scrollTop = msgsEl.scrollHeight;
  }
  function hideTyping() {
    if (typingRow) { typingRow.remove(); typingRow = null; }
  }
  function autosize() {
    inpEl.style.height = 'auto';
    inpEl.style.height = Math.min(inpEl.scrollHeight, 120) + 'px';
  }

  function send(text) {
    text = (text || '').trim();
    if (!text) return;
    addMsg('user', text);
    inpEl.value = '';
    autosize();
    sendEl.disabled = true;
    showTyping();
    fetch('./webhook', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sender: sender, message: text }),
    })
      .then(function (r) { return r.json(); })
      .then(function (replies) {
        hideTyping();
        (replies || []).forEach(function (r) {
          if (r.text) addMsg('bot', r.text);
          if (r.buttons && r.buttons.length) addButtons(r.buttons);
        });
      })
      .catch(function () {
        hideTyping();
        addMsg('bot', 'Sorry, something went wrong reaching the assistant.');
      })
      .finally(function () { sendEl.disabled = false; inpEl.focus(); });
  }

  sendEl.addEventListener('click', function () { send(inpEl.value); });
  inpEl.addEventListener('input', autosize);
  inpEl.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(inpEl.value); }
  });
  inpEl.focus();
})();
</script>
</body>
</html>
"""


class WebChatInput(RestInput):
    """Same message handling as the built-in REST channel, plus a browsable,
    shareable chat page at its own webhook root."""

    @classmethod
    def name(cls) -> Text:
        return "chat"

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[None]]
    ) -> Blueprint:
        module_type = inspect.getmodule(self)
        module_name = module_type.__name__ if module_type is not None else None
        webchat = Blueprint("webchat_{}".format(type(self).__name__), module_name)

        @webchat.route("/", methods=["GET"])
        async def chat_page(request: Request) -> HTTPResponse:
            return response.html(CHAT_PAGE)

        @webchat.route("/webhook", methods=["POST"])
        async def receive(request: Request) -> Union[ResponseStream, BaseHTTPResponse]:
            return await self.receive_messages(request, on_new_message)

        return webchat
