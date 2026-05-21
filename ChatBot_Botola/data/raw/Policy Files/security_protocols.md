&lt;!-- data/raw/security_protocols.md --&gt;
# BOTOLA PRO — SECURITY & ANTI-FRAUD PROTOCOLS

## Ticket Authentication

### Blockchain Verification
- Every ticket hash stored on private blockchain (Hyperledger Fabric)
- Immutable record of ownership chain
- QR code contains: ticket ID + timestamp + cryptographic signature
- Verification time: &lt;0.3 seconds

### Dynamic QR Security
- Refresh interval: 30 seconds
- Algorithm: HMAC-SHA256 with rotating key
- Offline validation: Turnstile can verify without internet (synced every 5 min)
- Screenshot detection: Pixel-pattern analysis at scan point

### Fraud Detection AI
- **Scalper detection**: Purchase velocity, IP clustering, payment pattern analysis
- **Duplicate detection**: Hash collision monitoring across all tickets
- **Bot detection**: CAPTCHA v3 + behavioral biometrics
- **Geolocation anomaly**: Flag if ticket scanned &gt;500km from purchase location

## Seller Verification (KYC)

### Required for selling
1. National ID (CIN) verification
2. Phone number verification (SMS + WhatsApp)
3. Bank account or CIH Mobile verification
4. Selfie with ID (liveness detection)
5. **Trust score &gt;50** to list tickets

### Trust score factors
| Factor | Weight | How to improve |
|--------|--------|--------------|
| Successful sales | 30% | Complete sales without disputes |
| Buyer ratings | 25% | Maintain &gt;4.5/5 stars |
| Response time | 15% | Answer buyer questions &lt;1 hour |
| Verification level | 15% | Complete all KYC steps |
| Account age | 10% | Older accounts score higher |
| No violations | 5% | Clean disciplinary record |

## Buyer Protection

### Escrow system
- Funds held by Botola Pro until ticket scanned at gate
- Seller paid within 24 hours of successful scan
- Dispute window: 48 hours after match

### Refund guarantees
- **Fake ticket**: Full refund + 500 MAD compensation
- **Wrong seat**: Full refund or upgrade
- **Match cancelled**: Automatic refund, no action needed
- **Not as described**: Partial refund based on severity

## Reporting Issues

### In-app reporting
- Fake listing: Tap "Report" → AI review within 15 minutes
- Bad seller: Rate &lt;3 stars → triggers manual review
- Security concern: Direct line to security team
- Urgent: Call +212 537 76 87 03 (24h)

### What happens to reported sellers?
| Violation | First offense | Repeat | Permanent |
|-----------|-------------|--------|-----------|
| Fake ticket | Account freeze 30 days | 90 days | Ban + legal action |
| Price gouging | Warning + price adjustment | 30-day listing ban | Permanent ban |
| No-show (didn't transfer) | Trust score -20 | -50 | Ban |
| Harassment | Immediate ban | — | Ban |

## Data Protection

### What we collect
- Identity: Name, CIN, phone, email (encrypted at rest)
- Financial: Bank details (tokenized, never stored raw)
- Behavioral: Purchase history, seat preferences (anonymized for AI)
- Location: Only during match day (for fraud detection)

### What we never do
- Sell data to third parties
- Use data for non-ticketing advertising
- Share with clubs without consent
- Store passwords in plain text

### Your rights (Moroccan Data Protection Law 09-08)
- Access: Request all your data
- Deletion: Delete account + data (30-day retention for legal)
- Portability: Export ticket history
- Correction: Update profile anytime

## Emergency Procedures

### If you witness fraud at the stadium
1. **Do not confront** — safety first
2. Report to nearest steward (orange vest)
3. Call security hotline: +212 537 76 87 03
4. Note: Section, row, seat, description
5. **Reward**: 1,000 MAD for tips leading to conviction

### System breach protocol
- Automatic: All dynamic QR keys rotated
- Manual: Stadium switches to paper backup + ID check
- Communication: SMS + app push to all affected users
- Compensation: Automatic credit for future matches