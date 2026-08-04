# iOS Trading App API Documentation

Complete API reference for iOS app to receive trading recommendations from MCP Agent

---

## Base URL

```
http://localhost:8000/api/v1/ios
http://localhost:8000/api/v1/agent
```

---

## Authentication

All requests require Bearer token:

```
Authorization: Bearer test-token
```

---

## iOS Message Endpoints (7)

### 1. Get Pending Messages
```
GET /ios/messages/pending?user_id=user_123
Authorization: Bearer test-token
```
Returns undelivered messages

### 2. Get All Messages
```
GET /ios/messages/all?user_id=user_123&limit=50
Authorization: Bearer test-token
```
Returns message history (newest first)

### 3. Mark as Delivered
```
POST /ios/messages/{message_id}/delivered?user_id=user_123
Authorization: Bearer test-token
```

### 4. Mark as Read
```
POST /ios/messages/{message_id}/read?user_id=user_123
Authorization: Bearer test-token
```

### 5. Archive Message
```
POST /ios/messages/{message_id}/archive?user_id=user_123
Authorization: Bearer test-token
```

### 6. Inbox Statistics
```
GET /ios/inbox/stats?user_id=user_123
Authorization: Bearer test-token
```
Returns: total, unread, pending, read, archived counts

### 7. Sync Updates (Polling)
```
GET /ios/updates/sync?user_id=user_123&last_sync=2026-05-27T14:00:00Z
Authorization: Bearer test-token
```
Get new messages since last sync (poll every 60 seconds)

---

## Analysis Endpoints (4)

### 1. Analyze Stock
```
POST /agent/analyze?ticker=AAPL&price=150
Authorization: Bearer test-token
```
Returns buy score, signal, thesis, targets

### 2. Get Watchlist
```
GET /agent/watchlist
Authorization: Bearer test-token
```
Returns list of monitored tickers

### 3. Add to Watchlist
```
POST /agent/watchlist/add?ticker=MSFT&buy_threshold=0.70
Authorization: Bearer test-token
```

### 4. Get Opportunities
```
GET /agent/opportunities?min_score=0.70
Authorization: Bearer test-token
```
Returns stocks with high buy scores

---

## Analytics Endpoints (2)

### 1. Top Signals
```
GET /ios/analytics/top-signals?user_id=user_123&limit=10
Authorization: Bearer test-token
```

### 2. Signal Summary
```
GET /ios/analytics/signal-summary?user_id=user_123
Authorization: Bearer test-token
```
Returns: total signals, strong buy, buy, hold counts, average score

---

## Swift Code Examples

### Get Pending Messages
```swift
let urlString = "http://localhost:8000/api/v1/ios/messages/pending?user_id=user_123"
var request = URLRequest(url: URL(string: urlString)!)
request.setValue("Bearer test-token", forHTTPHeaderField: "Authorization")

URLSession.shared.dataTask(with: request) { data, _, _ in
    let messages = try? JSONDecoder().decode([Message].self, from: data!)
}.resume()
```

### Sync Updates
```swift
let lastSync = ISO8601DateFormatter().string(from: Date())
let urlString = "http://localhost:8000/api/v1/ios/updates/sync?user_id=user_123&last_sync=\(lastSync)"
var request = URLRequest(url: URL(string: urlString)!)
request.setValue("Bearer test-token", forHTTPHeaderField: "Authorization")

URLSession.shared.dataTask(with: request) { data, _, _ in
    let response = try? JSONDecoder().decode(SyncResponse.self, from: data!)
    // Process new messages
}.resume()
```

### Mark as Read
```swift
let urlString = "http://localhost:8000/api/v1/ios/messages/msg_1/read?user_id=user_123"
var request = URLRequest(url: URL(string: urlString)!)
request.httpMethod = "POST"
request.setValue("Bearer test-token", forHTTPHeaderField: "Authorization")

URLSession.shared.dataTask(with: request).resume()
```

---

## Message Models

```swift
struct Message: Codable, Identifiable {
    let id: String
    let ticker: String
    let buyScore: Double
    let buySignal: String
    let title: String
    let body: String
    let thesis: String
    let keyFactors: [String]
    let confidence: String
    let status: String
    let createdAt: String
}

struct SyncResponse: Codable {
    let status: String
    let newMessages: Int
    let messages: [Message]
    let syncTime: String
    let nextSyncInSeconds: Int
}

struct InboxStats: Codable {
    let totalMessages: Int
    let unread: Int
    let pending: Int
    let read: Int
    let archived: Int
}
```

---

## Testing

```bash
# Get pending messages
curl -H "Authorization: Bearer test-token" \
  "http://localhost:8000/api/v1/ios/messages/pending?user_id=user_123"

# Mark as read
curl -X POST -H "Authorization: Bearer test-token" \
  "http://localhost:8000/api/v1/ios/messages/msg_1/read?user_id=user_123"

# Get stats
curl -H "Authorization: Bearer test-token" \
  "http://localhost:8000/api/v1/ios/inbox/stats?user_id=user_123"
```

---

**11 Total Endpoints | 7 Message + 4 Analysis | Bearer Token Auth**
