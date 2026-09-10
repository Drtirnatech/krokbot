# Design Spec: MarinaBox Browser & Computer Use Capability for KrokBot

**Date**: 2026-09-10  
**Author**: Antigravity AI  
**Status**: Draft for User Approval  

---

## 1. Executive Summary

This design enables **MarinaBox Computer Use Browser GUI automation** within KrokBot, allowing the agent to perform real browser navigation, mouse movement, typing, clicking, and screen capturing. Additionally, it fixes the hardcoded system diagnostic behavior in `KrokBotAgent` so KrokBot routes requests dynamically based on user intent.

---

## 2. Key Requirements & Capabilities

1. **MarinaBox `ComputerTool` Integration**:
   - Wrap `marinabox.computer_use.tools.computer.ComputerTool` within `ToolRegistry`.
   - Support browser actions: `screenshot`, `navigate`, `left_click`, `type`, `key`, `scroll`, `wait`, `mouse_move`.
   - Fix Windows `strftime` platform compatibility issue in `marinabox.computer_use.loop`.

2. **Dynamic Prompt Routing**:
   - Remove forced system metric/drive partition checks on every prompt.
   - Route tasks dynamically:
     - **System/Drive Audits**: Execute bridge metrics & drive partition script only when asked about health/storage.
     - **Web/Browser Tasks**: Execute `ComputerTool` browser actions or web fetch scripts when asked to check weather, browse pages, or search information.
     - **General Queries**: Provide standard conversational responses.

3. **Web Dashboard Support**:
   - Update `POST /api/chat` and Web UI (`dashboard/index.html`) to render base64 browser screenshots alongside text responses when browser automation is triggered.

---

## 3. Component Design & Changes

```
┌─────────────────────────────────────────────────────────────┐
│                       Web UI (5150)                         │
└──────────────┬──────────────────────────────▲───────────────┘
               │ POST /api/chat               │ Base64 Image & Text
               ▼                              │
┌─────────────────────────────────────────────────────────────┐
│                      KrokBotAgent                           │
│  - Dynamic Intent Router (Diagnostics vs Web/Browser vs QA) │
└──────────────┬──────────────────────────────▲───────────────┘
               │                              │
               ▼                              │
┌─────────────────────────────────────────────────────────────┐
│                      ToolRegistry                           │
├──────────────────────────────┬──────────────────────────────┤
│ Host Bridge (Metrics/Drives) │ MarinaBox ComputerTool       │
│ - /api/v1/system/summary     │ - screenshot, left_click     │
│ - /api/v1/system/storage     │ - type, key, scroll, navigate│
└──────────────────────────────┴──────────────────────────────┘
```

### Affected Files
1. **`krokbot/sandbox/browser.py` [NEW]**: High-level wrapper over `marinabox.computer_use.tools.computer.ComputerTool` with fallback to local web fetcher.
2. **`krokbot/agent/tools.py` [MODIFY]**: Expose `browser_action(...)` and `web_browse(...)` methods in `ToolRegistry`.
3. **`krokbot/agent/core.py` [MODIFY]**: Implement dynamic intent classifier/routing in `run_task(...)` instead of hardcoded diagnostics.
4. **`krokbot/dashboard/app.py` & `index.html` [MODIFY]**: Handle screenshot rendering in chat UI.
5. **`tests/test_browser.py` [NEW]**: Unit tests for browser actions and dynamic prompt routing.

---

## 4. Verification Plan

* **Unit Tests**: Run `pytest tests/` ensuring all bridge, sandbox, browser, and agent tests pass.
* **Manual Verification**: 
  - Prompt: *"What is the weather in New York?"* -> Verify agent triggers browser/web tool and returns weather without forcing drive diagnostic reports.
  - Prompt: *"Inspect my C:, D:, and E: drives"* -> Verify agent returns complete drive storage capacity breakdown.

---
