# CMO Agent Chat Console

A modern Next.js chat interface for your CMO Agent, featuring structured AI cards, real-time streaming, and comprehensive campaign management.

## Features

- 🎯 **Structured AI Cards**: Campaign briefs, simulation packs, outbox previews, and more
- 🔄 **Real-time Streaming**: Server-sent events for live updates and LangGraph node events
- 🎚️ **Autopilot Controls**: L0-L4 autonomy levels with inline budget management
- 🎨 **Modern UI**: Built with Next.js, TypeScript, and Tailwind CSS
- 📊 **Live Inspector**: RunState, graph visualization, metrics, and event logs
- 💬 **Chat-driven UX**: Natural language commands with structured responses
- ⚡ **Enhanced UX**: Connection status indicators, loading states, and error feedback
- ♿ **Accessible**: ARIA attributes, keyboard shortcuts, and screen reader support
- 🔒 **Robust**: Duplicate event prevention, error recovery, and graceful fallbacks

## Quick Start

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Set Up Environment (Optional)

```bash
cp env.example .env.local
```

Edit `.env.local` to point to your FastAPI backend:

```env
# Backend API URL (optional - will use mock data if not set)
API_URL=http://localhost:8000

# Next.js public API base for client-side requests
NEXT_PUBLIC_API_BASE=http://localhost:3000
```

### 3. Run Development Server

```bash
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000) to see the console.

## Architecture

### Frontend Stack

- **Next.js 14** with App Router
- **TypeScript** for type safety
- **Tailwind CSS** for styling
- **Server-Sent Events** for real-time streaming
- **Structured AI Cards** for rich interactions

### Backend Integration

- **FastAPI Proxy**: API routes proxy to your backend
- **Mock Mode**: Works without backend for development
- **SSE Streaming**: Real-time events and LangGraph node updates
- **Type Safety**: Shared Pydantic schemas via OpenAPI

## Usage Examples

### Basic Chat Commands

```
"Find 2k Python maintainers active in the last 90 days, sequence 123"
→ Returns Campaign Brief card with ICP, limits, and risks

"Preflight then run with $50/day cap"
→ Returns Simulation Pack with forecasts and warnings
→ Followed by live execution with streaming events

"Show outbox samples and approve rule"
→ Returns Outbox card with email previews and bulk actions

"Why did open rates dip?"
→ Returns Explain card with root cause analysis
```

### Autopilot Levels

- **L0 Manual**: Review and approve all actions
- **L1 Stage-gated**: Approve at discovery/personalization/send stages
- **L2 Budgeted**: Run within hard caps, escalate exceptions
- **L3 Self-tuning**: Adjust pacing/variants within policy
- **L4 Autonomous**: Full automation with periodic reports

### AI Card Types

- **Campaign Brief**: Goal, ICP, limits, risks, YAML config
- **Simulation Pack**: Reply forecasts, deliverability, cost estimates
- **Outbox**: Email samples with evidence chips and policy status
- **Run Summary**: Metrics, status, progress tracking
- **Error Group**: Grouped errors with retry suggestions
- **Policy Diff**: Configuration changes with impact analysis

## Development

### Project Structure

```
frontend/
├── app/                    # Next.js App Router
│   ├── (console)/         # Console layout group
│   │   ├── layout.tsx     # 3-column layout
│   │   └── threads/[id]/  # Chat thread pages
│   ├── api/               # API routes (proxy to backend)
│   └── globals.css        # Global styles
├── components/            # React components
│   ├── cards/            # AI card components
│   ├── ChatComposer.tsx  # Message input with controls
│   ├── MessageBubble.tsx # Message display
│   ├── Sidebar.tsx       # Thread/campaign switcher
│   └── Inspector.tsx     # Debug panel
├── lib/
│   └── useSSE.ts         # Server-sent events hook
└── types/
    └── index.ts          # TypeScript definitions
```

### Adding New Card Types

1. Add type definition to `types/index.ts`:

```typescript
export interface MyNewCard {
  type: "my_new_card";
  data: any;
  actions: ActionButton[];
}
```

2. Create component in `components/cards/`:

```typescript
export function MyNewCardView({ card }: { card: MyNewCard }) {
  return <div>...</div>;
}
```

3. Add to `MessageBubble.tsx`:

```typescript
{
  message.card?.type === "my_new_card" && <MyNewCardView card={message.card} />;
}
```

### Backend Integration

The console expects these FastAPI endpoints:

- `POST /chat` - Send chat message, start LangGraph execution
- `GET /threads/{id}/events` - SSE stream of messages and events
- `POST /actions` - Execute card actions (approve, edit, etc.)

Example FastAPI route:

```python
@router.get("/threads/{thread_id}/events")
async def stream_thread(thread_id: str):
    async def generate():
        yield "retry: 1500\n\n"
        async for event in langgraph_events(thread_id):
            yield f"data: {json.dumps(event)}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

## Production Deployment

### Build for Production

```bash
npm run build
npm start
```

### Environment Variables

```env
API_URL=https://your-backend.com
NEXT_PUBLIC_API_BASE=https://your-frontend.com
```

### Docker Support

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

## Audit Improvements

Based on the comprehensive front-end audit, the following enhancements have been implemented:

### 🔧 **Core Fixes**

- **SSE Duplication Bug**: Fixed event handling to prevent duplicate messages in chat
- **Thread History Loading**: Added automatic loading of existing thread messages on page load
- **Error Feedback**: All API errors now surface visibly to users with user-friendly messages
- **Connection Status**: Real-time SSE connection indicator with reconnection feedback

### 🎨 **UX Enhancements**

- **Autopilot Tooltips**: Hover tooltips explain each autonomy level (L0-L4)
- **Policy Status Icons**: Visual indicators (✓, ⚠️, ✗) for email policy compliance
- **Loading States**: Spinners and loading indicators throughout the interface
- **Error Recovery**: Action buttons show retry states and error messages

### ♿ **Accessibility**

- **ARIA Attributes**: Proper labeling and screen reader support
- **Keyboard Shortcuts**: Cmd/Ctrl+Enter to send, Shift+Enter for new lines
- **Focus Management**: Logical tab order and focus indicators
- **Semantic HTML**: Proper form labels and button descriptions

### 🛡️ **Robustness**

- **Graceful Fallbacks**: Mock data when backend unavailable
- **Connection Recovery**: Automatic SSE reconnection with exponential backoff
- **Input Validation**: Budget limits and proper form validation
- **Memory Management**: Efficient event handling without memory leaks

These improvements ensure the console is production-ready with enterprise-grade reliability and user experience.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
