# iOS Trading App - Complete Integration Guide

Complete guide to integrate all trading system APIs into an iOS app project.

---

## Table of Contents

1. [Project Setup](#project-setup)
2. [API Architecture](#api-architecture)
3. [Data Models](#data-models)
4. [API Client Implementation](#api-client-implementation)
5. [Feature Implementation](#feature-implementation)
6. [UI Integration](#ui-integration)
7. [Testing](#testing)
8. [Deployment](#deployment)

---

## Project Setup

### Step 1: Create iOS Project

```bash
# Create new project in Xcode
# File → New → Project → iOS → App
# Language: Swift
# Interface: SwiftUI
```

### Step 2: Add Dependencies

Using SPM (Swift Package Manager):

```swift
// Package.swift dependencies
.package(url: "https://github.com/Alamofire/Alamofire.git", from: "5.0"),
.package(url: "https://github.com/groue/GRDB.swift.git", from: "5.0")
```

Or via CocoaPods:

```ruby
# Podfile
pod 'Alamofire', '~> 5.0'
pod 'GRDB.swift', '~> 5.0'
```

### Step 3: Project Structure

```
TradingApp/
├── Models/
│   ├── Message.swift
│   ├── Stock.swift
│   ├── Analysis.swift
│   └── Signal.swift
├── Networking/
│   ├── APIClient.swift
│   ├── APIEndpoints.swift
│   └── NetworkManager.swift
├── Services/
│   ├── MessageService.swift
│   ├── AnalysisService.swift
│   ├── AuthService.swift
│   └── StorageService.swift
├── ViewModels/
│   ├── InboxViewModel.swift
│   ├── AnalysisViewModel.swift
│   ├── WatchlistViewModel.swift
│   └── DashboardViewModel.swift
├── Views/
│   ├── InboxView.swift
│   ├── MessageDetailView.swift
│   ├── AnalysisView.swift
│   ├── WatchlistView.swift
│   └── DashboardView.swift
├── Database/
│   ├── DatabaseManager.swift
│   └── Migrations.swift
└── App.swift
```

---

## API Architecture

### Base Configuration

```swift
// Networking/APIClient.swift

import Foundation
import Alamofire

class APIClient {
    static let shared = APIClient()
    
    let baseURL = "http://localhost:8000/api/v1"  // Change for production
    let token = "test-token"  // Store securely in Keychain
    
    private init() {}
    
    // MARK: - Request Building
    
    func request<T: Decodable>(
        method: HTTPMethod,
        endpoint: String,
        parameters: [String: Any]? = nil,
        completion: @escaping (Result<T, Error>) -> Void
    ) {
        let url = "\(baseURL)\(endpoint)"
        var headers: HTTPHeaders = [
            "Authorization": "Bearer \(token)",
            "Content-Type": "application/json"
        ]
        
        AF.request(
            url,
            method: method,
            parameters: parameters,
            encoding: URLEncoding.default,
            headers: headers
        )
        .validate()
        .responseDecodable(of: T.self) { response in
            completion(response.result)
        }
    }
}
```

---

## Data Models

### Message Model

```swift
// Models/Message.swift

import Foundation

struct Message: Identifiable, Codable {
    let id: String
    let userId: String
    let ticker: String
    let messageType: MessageType
    let buyScore: Double
    let buySignal: String
    let title: String
    let body: String
    let thesis: String
    let keyFactors: [String]
    let targets: PriceTargets?
    let confidence: String
    let status: MessageStatus
    let createdAt: Date
    let deliveredAt: Date?
    let readAt: Date?
    
    enum MessageType: String, Codable {
        case buySignal = "buy_signal"
        case analysis = "analysis"
        case alert = "alert"
        case watchlistUpdate = "watchlist_update"
    }
    
    enum MessageStatus: String, Codable {
        case pending = "pending"
        case delivered = "delivered"
        case read = "read"
        case archived = "archived"
    }
    
    enum CodingKeys: String, CodingKey {
        case id, userId = "user_id", ticker, messageType = "message_type"
        case buyScore = "buy_score", buySignal = "buy_signal", title, body, thesis
        case keyFactors = "key_factors", targets, confidence, status
        case createdAt = "created_at", deliveredAt = "delivered_at", readAt = "read_at"
    }
}

struct PriceTargets: Codable {
    let upside: Double
    let downside: Double
}
```

### Stock Analysis Model

```swift
// Models/Analysis.swift

import Foundation

struct StockAnalysis: Identifiable, Codable {
    let id: String = UUID().uuidString
    let ticker: String
    let price: Double
    let buyScore: Double
    let buySignal: String
    let thesis: String
    let keyFactors: [String]
    let confidence: String
    let technicalScore: Double
    let sentimentScore: Double
    let mlScore: Double
    let strategyScore: Double
    let marketScore: Double
    let targets: PriceTargets?
    let timestamp: Date
    
    enum CodingKeys: String, CodingKey {
        case ticker, price
        case buyScore = "buy_score"
        case buySignal = "buy_signal"
        case thesis, confidence, targets, timestamp
        case keyFactors = "key_factors"
        case technicalScore = "technical_score"
        case sentimentScore = "sentiment_score"
        case mlScore = "ml_score"
        case strategyScore = "strategy_score"
        case marketScore = "market_score"
    }
}
```

### Watchlist Model

```swift
// Models/Stock.swift

import Foundation

struct WatchlistItem: Identifiable, Codable {
    let id: String = UUID().uuidString
    let ticker: String
    let buyThreshold: Double
    let addedDate: Date
    let lastAnalysis: StockAnalysis?
    
    enum CodingKeys: String, CodingKey {
        case ticker
        case buyThreshold = "buy_threshold"
        case addedDate = "added_date"
        case lastAnalysis = "last_analysis"
    }
}
```

---

## API Client Implementation

### Messages API

```swift
// Services/MessageService.swift

import Foundation
import Alamofire

class MessageService {
    static let shared = MessageService()
    
    private let apiClient = APIClient.shared
    private let userId = UIDevice.current.identifierForVendor?.uuidString ?? "user_default"
    
    // MARK: - Get Pending Messages
    
    func getPendingMessages(completion: @escaping (Result<[Message], Error>) -> Void) {
        apiClient.request(
            method: .get,
            endpoint: "/ios/messages/pending?user_id=\(userId)",
            completion: completion
        )
    }
    
    // MARK: - Get All Messages
    
    func getAllMessages(limit: Int = 100, completion: @escaping (Result<[Message], Error>) -> Void) {
        apiClient.request(
            method: .get,
            endpoint: "/ios/messages/all?user_id=\(userId)&limit=\(limit)",
            completion: completion
        )
    }
    
    // MARK: - Get Single Message
    
    func getMessage(_ messageId: String, completion: @escaping (Result<Message, Error>) -> Void) {
        apiClient.request(
            method: .get,
            endpoint: "/ios/messages/\(messageId)?user_id=\(userId)",
            completion: completion
        )
    }
    
    // MARK: - Mark as Delivered
    
    func markDelivered(_ messageId: String, completion: @escaping (Result<DeliveryResponse, Error>) -> Void) {
        apiClient.request(
            method: .post,
            endpoint: "/ios/messages/\(messageId)/delivered?user_id=\(userId)",
            completion: completion
        )
    }
    
    // MARK: - Mark as Read
    
    func markRead(_ messageId: String, completion: @escaping (Result<ReadResponse, Error>) -> Void) {
        apiClient.request(
            method: .post,
            endpoint: "/ios/messages/\(messageId)/read?user_id=\(userId)",
            completion: completion
        )
    }
    
    // MARK: - Archive Message
    
    func archiveMessage(_ messageId: String, completion: @escaping (Result<ArchiveResponse, Error>) -> Void) {
        apiClient.request(
            method: .post,
            endpoint: "/ios/messages/\(messageId)/archive?user_id=\(userId)",
            completion: completion
        )
    }
    
    // MARK: - Inbox Stats
    
    func getInboxStats(completion: @escaping (Result<InboxStats, Error>) -> Void) {
        apiClient.request(
            method: .get,
            endpoint: "/ios/inbox/stats?user_id=\(userId)",
            completion: completion
        )
    }
    
    // MARK: - Sync Updates
    
    func syncUpdates(since lastSync: Date?, completion: @escaping (Result<SyncResponse, Error>) -> Void) {
        let queryParam = lastSync.map { "last_sync=\($0.ISO8601Format())" } ?? ""
        apiClient.request(
            method: .get,
            endpoint: "/ios/updates/sync?user_id=\(userId)&\(queryParam)",
            completion: completion
        )
    }
}

// Response Models
struct DeliveryResponse: Codable {
    let status: String
    let messageId: String
    let deliveredAt: Date
    
    enum CodingKeys: String, CodingKey {
        case status
        case messageId = "message_id"
        case deliveredAt = "delivered_at"
    }
}

struct ReadResponse: Codable {
    let status: String
    let messageId: String
    let readAt: Date
    
    enum CodingKeys: String, CodingKey {
        case status
        case messageId = "message_id"
        case readAt = "read_at"
    }
}

struct ArchiveResponse: Codable {
    let status: String
    let messageId: String
    let archived: Bool
    
    enum CodingKeys: String, CodingKey {
        case status
        case messageId = "message_id"
        case archived
    }
}

struct InboxStats: Codable {
    let totalMessages: Int
    let unread: Int
    let pending: Int
    let read: Int
    let archived: Int
    
    enum CodingKeys: String, CodingKey {
        case totalMessages = "total_messages"
        case unread, pending, read, archived
    }
}

struct SyncResponse: Codable {
    let status: String
    let newMessages: Int
    let messages: [Message]
    let syncTime: Date
    let nextSyncInSeconds: Int
    
    enum CodingKeys: String, CodingKey {
        case status
        case newMessages = "new_messages"
        case messages
        case syncTime = "sync_time"
        case nextSyncInSeconds = "next_sync_in_seconds"
    }
}
```

### Analysis API

```swift
// Services/AnalysisService.swift

import Foundation
import Alamofire

class AnalysisService {
    static let shared = AnalysisService()
    
    private let apiClient = APIClient.shared
    
    // MARK: - Analyze Stock
    
    func analyzeStock(
        ticker: String,
        price: Double,
        completion: @escaping (Result<StockAnalysis, Error>) -> Void
    ) {
        apiClient.request(
            method: .post,
            endpoint: "/agent/analyze?ticker=\(ticker)&price=\(price)",
            completion: completion
        )
    }
    
    // MARK: - Get Watchlist
    
    func getWatchlist(completion: @escaping (Result<WatchlistResponse, Error>) -> Void) {
        apiClient.request(
            method: .get,
            endpoint: "/agent/watchlist",
            completion: completion
        )
    }
    
    // MARK: - Add to Watchlist
    
    func addToWatchlist(
        ticker: String,
        buyThreshold: Double = 0.70,
        completion: @escaping (Result<AddWatchlistResponse, Error>) -> Void
    ) {
        apiClient.request(
            method: .post,
            endpoint: "/agent/watchlist/add?ticker=\(ticker)&buy_threshold=\(buyThreshold)",
            completion: completion
        )
    }
    
    // MARK: - Get Opportunities
    
    func getOpportunities(
        minScore: Double = 0.70,
        completion: @escaping (Result<[StockAnalysis], Error>) -> Void
    ) {
        apiClient.request(
            method: .get,
            endpoint: "/agent/opportunities?min_score=\(minScore)",
            completion: completion
        )
    }
    
    // MARK: - Get Analysis History
    
    func getAnalysisHistory(
        ticker: String,
        days: Int = 30,
        completion: @escaping (Result<[StockAnalysis], Error>) -> Void
    ) {
        apiClient.request(
            method: .get,
            endpoint: "/agent/history/\(ticker)?days=\(days)",
            completion: completion
        )
    }
    
    // MARK: - Get Performance Metrics
    
    func getPerformanceMetrics(completion: @escaping (Result<PerformanceMetrics, Error>) -> Void) {
        apiClient.request(
            method: .get,
            endpoint: "/agent/performance",
            completion: completion
        )
    }
}

// Response Models
struct WatchlistResponse: Codable {
    let watchlist: [WatchlistItem]
}

struct AddWatchlistResponse: Codable {
    let status: String
    let ticker: String
    let message: String
}

struct PerformanceMetrics: Codable {
    let totalAnalyzed: Int
    let averageBuyScore: Double
    let strongBuyCount: Int
    let buyCount: Int
    let holdCount: Int
    let accuracy: Double
    
    enum CodingKeys: String, CodingKey {
        case totalAnalyzed = "total_analyzed"
        case averageBuyScore = "average_buy_score"
        case strongBuyCount = "strong_buy_count"
        case buyCount = "buy_count"
        case holdCount = "hold_count"
        case accuracy
    }
}
```

---

## Feature Implementation

### Inbox Feature

```swift
// ViewModels/InboxViewModel.swift

import Foundation

class InboxViewModel: ObservableObject {
    @Published var messages: [Message] = []
    @Published var isLoading = false
    @Published var error: Error?
    @Published var unreadCount = 0
    @Published var lastSync: Date?
    
    private let messageService = MessageService.shared
    private var syncTimer: Timer?
    
    // MARK: - Load Inbox
    
    func loadInbox() {
        isLoading = true
        messageService.getAllMessages { [weak self] result in
            DispatchQueue.main.async {
                self?.isLoading = false
                switch result {
                case .success(let messages):
                    self?.messages = messages
                    self?.updateUnreadCount()
                case .failure(let error):
                    self?.error = error
                }
            }
        }
    }
    
    // MARK: - Sync Updates (Polling)
    
    func startPolling(interval: TimeInterval = 60) {
        syncTimer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { [weak self] _ in
            self?.syncMessages()
        }
    }
    
    func stopPolling() {
        syncTimer?.invalidate()
    }
    
    private func syncMessages() {
        messageService.syncUpdates(since: lastSync) { [weak self] result in
            DispatchQueue.main.async {
                switch result {
                case .success(let response):
                    self?.messages.insert(contentsOf: response.messages, at: 0)
                    self?.lastSync = response.syncTime
                    self?.updateUnreadCount()
                case .failure(let error):
                    self?.error = error
                }
            }
        }
    }
    
    // MARK: - Message Actions
    
    func markAsRead(_ message: Message) {
        messageService.markRead(message.id) { [weak self] result in
            if case .success = result {
                DispatchQueue.main.async {
                    if let index = self?.messages.firstIndex(where: { $0.id == message.id }) {
                        self?.messages[index].readAt = Date()
                        self?.updateUnreadCount()
                    }
                }
            }
        }
    }
    
    func archiveMessage(_ message: Message) {
        messageService.archiveMessage(message.id) { [weak self] result in
            if case .success = result {
                DispatchQueue.main.async {
                    self?.messages.removeAll { $0.id == message.id }
                }
            }
        }
    }
    
    private func updateUnreadCount() {
        unreadCount = messages.filter { $0.status == .pending }.count
    }
}
```

### Analysis Feature

```swift
// ViewModels/AnalysisViewModel.swift

import Foundation

class AnalysisViewModel: ObservableObject {
    @Published var selectedStock: String = "AAPL"
    @Published var stockPrice: Double = 150
    @Published var analysis: StockAnalysis?
    @Published var opportunities: [StockAnalysis] = []
    @Published var isLoading = false
    @Published var error: Error?
    
    private let analysisService = AnalysisService.shared
    
    // MARK: - Analyze Stock
    
    func analyzeStock() {
        isLoading = true
        analysisService.analyzeStock(ticker: selectedStock, price: stockPrice) { [weak self] result in
            DispatchQueue.main.async {
                self?.isLoading = false
                switch result {
                case .success(let analysis):
                    self?.analysis = analysis
                case .failure(let error):
                    self?.error = error
                }
            }
        }
    }
    
    // MARK: - Get Top Opportunities
    
    func loadOpportunities(minScore: Double = 0.70) {
        isLoading = true
        analysisService.getOpportunities(minScore: minScore) { [weak self] result in
            DispatchQueue.main.async {
                self?.isLoading = false
                switch result {
                case .success(let opportunities):
                    self?.opportunities = opportunities
                case .failure(let error):
                    self?.error = error
                }
            }
        }
    }
}
```

---

## UI Integration

### Inbox View

```swift
// Views/InboxView.swift

import SwiftUI

struct InboxView: View {
    @StateObject private var viewModel = InboxViewModel()
    @State private var selectedMessage: Message?
    
    var body: some View {
        NavigationView {
            ZStack {
                if viewModel.messages.isEmpty {
                    VStack(spacing: 20) {
                        Image(systemName: "tray")
                            .font(.system(size: 50))
                            .foregroundColor(.gray)
                        Text("No Messages")
                            .font(.headline)
                        Text("Check back later for trading recommendations")
                            .font(.caption)
                            .foregroundColor(.gray)
                    }
                } else {
                    List {
                        ForEach(viewModel.messages) { message in
                            NavigationLink(destination: MessageDetailView(message: message)) {
                                MessageRowView(message: message)
                                    .onAppear {
                                        if message.status == .pending {
                                            viewModel.markAsRead(message)
                                        }
                                    }
                            }
                            .swipeActions(edge: .trailing) {
                                Button(role: .destructive) {
                                    viewModel.archiveMessage(message)
                                } label: {
                                    Label("Archive", systemImage: "archivebox")
                                }
                            }
                        }
                    }
                }
                
                if viewModel.isLoading {
                    ProgressView()
                }
            }
            .navigationTitle("Inbox")
            .badge(viewModel.unreadCount)
            .onAppear {
                viewModel.loadInbox()
                viewModel.startPolling(interval: 60)
            }
            .onDisappear {
                viewModel.stopPolling()
            }
        }
    }
}

struct MessageRowView: View {
    let message: Message
    
    var signalColor: Color {
        switch message.buySignal {
        case "STRONG_BUY":
            return .red
        case "BUY":
            return .orange
        default:
            return .yellow
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading) {
                    Text(message.title)
                        .font(.headline)
                    Text(message.body)
                        .font(.caption)
                        .foregroundColor(.gray)
                        .lineLimit(2)
                }
                
                Spacer()
                
                VStack(alignment: .trailing) {
                    Text("\(Int(message.buyScore * 100))%")
                        .font(.headline)
                        .foregroundColor(signalColor)
                    
                    Text(message.confidence)
                        .font(.caption2)
                        .foregroundColor(.gray)
                }
            }
            
            HStack(spacing: 4) {
                ForEach(message.keyFactors.prefix(2), id: \.self) { factor in
                    Text(factor)
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.blue.opacity(0.1))
                        .cornerRadius(4)
                }
            }
        }
        .padding(.vertical, 8)
    }
}
```

### Analysis View

```swift
// Views/AnalysisView.swift

import SwiftUI

struct AnalysisView: View {
    @StateObject private var viewModel = AnalysisViewModel()
    
    var body: some View {
        NavigationView {
            Form {
                Section("Stock") {
                    TextField("Ticker", text: $viewModel.selectedStock)
                        .textInputAutocapitalization(.characters)
                    
                    Stepper(
                        "Price: $\(String(format: "%.2f", viewModel.stockPrice))",
                        value: $viewModel.stockPrice,
                        in: 1...1000,
                        step: 0.50
                    )
                }
                
                Button("Analyze") {
                    viewModel.analyzeStock()
                }
                .disabled(viewModel.isLoading)
                
                if let analysis = viewModel.analysis {
                    Section("Analysis") {
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                Text("Buy Score")
                                Spacer()
                                Text("\(Int(analysis.buyScore * 100))%")
                                    .font(.headline)
                                    .foregroundColor(analysis.buyScore > 0.7 ? .green : .orange)
                            }
                            
                            HStack {
                                Text("Signal")
                                Spacer()
                                Text(analysis.buySignal)
                                    .font(.headline)
                            }
                            
                            HStack {
                                Text("Confidence")
                                Spacer()
                                Text(analysis.confidence)
                            }
                            
                            Divider()
                            
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Thesis")
                                    .font(.subheadline)
                                    .fontWeight(.semibold)
                                Text(analysis.thesis)
                                    .font(.caption)
                                    .foregroundColor(.gray)
                            }
                            
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Key Factors")
                                    .font(.subheadline)
                                    .fontWeight(.semibold)
                                
                                ForEach(analysis.keyFactors, id: \.self) { factor in
                                    HStack(spacing: 8) {
                                        Image(systemName: "checkmark.circle.fill")
                                            .foregroundColor(.green)
                                        Text(factor)
                                            .font(.caption)
                                    }
                                }
                            }
                        }
                    }
                }
            }
            .navigationTitle("Stock Analysis")
        }
    }
}
```

---

## Testing

### Unit Tests

```swift
// Tests/MessageServiceTests.swift

import XCTest
@testable import TradingApp

class MessageServiceTests: XCTestCase {
    
    let messageService = MessageService.shared
    
    func testGetPendingMessages() {
        let expectation = XCTestExpectation(description: "Fetch pending messages")
        
        messageService.getPendingMessages { result in
            switch result {
            case .success(let messages):
                XCTAssertGreaterThanOrEqual(messages.count, 0)
                expectation.fulfill()
            case .failure(let error):
                XCTFail("Failed with error: \(error)")
            }
        }
        
        wait(for: [expectation], timeout: 10.0)
    }
    
    func testMarkAsRead() {
        let messageId = "msg_1"
        let expectation = XCTestExpectation(description: "Mark message as read")
        
        messageService.markRead(messageId) { result in
            switch result {
            case .success(let response):
                XCTAssertEqual(response.status, "success")
                expectation.fulfill()
            case .failure(let error):
                XCTFail("Failed with error: \(error)")
            }
        }
        
        wait(for: [expectation], timeout: 10.0)
    }
}
```

---

## Deployment

### Configuration for Production

```swift
// Config.swift

import Foundation

struct Config {
    #if DEBUG
    static let baseURL = "http://localhost:8000"
    static let apiToken = "test-token"
    #else
    static let baseURL = "https://trading-api.example.com"
    static let apiToken = ProcessInfo.processInfo.environment["API_TOKEN"] ?? ""
    #endif
    
    static let apiVersion = "v1"
    static let syncInterval: TimeInterval = 60
}
```

### Security

```swift
// Services/KeychainService.swift

import Security

class KeychainService {
    static let shared = KeychainService()
    
    func saveToken(_ token: String, for key: String) {
        let data = token.data(using: .utf8)!
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecValueData as String: data
        ]
        
        SecItemDelete(query as CFDictionary)
        SecItemAdd(query as CFDictionary, nil)
    }
    
    func retrieveToken(for key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true
        ]
        
        var result: AnyObject?
        SecItemCopyMatching(query as CFDictionary, &result)
        
        if let data = result as? Data {
            return String(data: data, encoding: .utf8)
        }
        return nil
    }
}
```

---

## API Endpoints Quick Reference

### Messages
- `GET /ios/messages/pending` - Get undelivered messages
- `GET /ios/messages/all` - Get message inbox
- `POST /ios/messages/{id}/read` - Mark as read
- `POST /ios/messages/{id}/delivered` - Mark as delivered
- `POST /ios/messages/{id}/archive` - Archive message
- `GET /ios/inbox/stats` - Get inbox statistics
- `GET /ios/updates/sync` - Sync new messages

### Analysis
- `POST /agent/analyze` - Analyze stock
- `GET /agent/watchlist` - Get watchlist
- `POST /agent/watchlist/add` - Add to watchlist
- `GET /agent/opportunities` - Get buy opportunities
- `GET /agent/history/{ticker}` - Get analysis history
- `GET /agent/performance` - Get performance metrics

### Health
- `GET /health` - System health check
- `GET /api/docs` - Swagger documentation

---

## Launch Checklist

- [ ] Configure API endpoint for production
- [ ] Store API token securely in Keychain
- [ ] Implement user authentication
- [ ] Set up local database (GRDB)
- [ ] Test all API endpoints
- [ ] Implement error handling
- [ ] Add crash reporting (Firebase)
- [ ] Set up analytics
- [ ] Enable HTTPS/SSL pinning
- [ ] Test on physical device
- [ ] Configure release signing
- [ ] Submit to App Store

---

## Support & Documentation

- **API Docs**: `http://localhost:8000/api/docs`
- **GitHub**: Your repository
- **Backend Issues**: Check server logs

