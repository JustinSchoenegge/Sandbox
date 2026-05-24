PRICES_AS_OF = "May 2026"

STOCKS = [
    {
        "name": "Apple",
        "ticker": "AAPL",
        "sector": "Technology",
        "price": 210,
        "hint": "$100 – $500",
        "fact": "Apple was the first US company to hit a $3 trillion market cap.",
    },
    {
        "name": "NVIDIA",
        "ticker": "NVDA",
        "sector": "Semiconductors",
        "price": 130,
        "hint": "$100 – $500",
        "fact": "NVIDIA's GPUs power most of the world's AI model training.",
    },
    {
        "name": "Tesla",
        "ticker": "TSLA",
        "sector": "Electric Vehicles",
        "price": 250,
        "hint": "$100 – $500",
        "fact": "Tesla delivers over 1.8 million vehicles per year globally.",
    },
    {
        "name": "Amazon",
        "ticker": "AMZN",
        "sector": "E-Commerce / Cloud",
        "price": 220,
        "hint": "$100 – $500",
        "fact": "Amazon Web Services generates more profit than the entire retail business.",
    },
    {
        "name": "Microsoft",
        "ticker": "MSFT",
        "sector": "Technology",
        "price": 430,
        "hint": "$100 – $500",
        "fact": "Microsoft invested $13 billion into OpenAI, the company behind ChatGPT.",
    },
    {
        "name": "Meta",
        "ticker": "META",
        "sector": "Social Media",
        "price": 590,
        "hint": "$500 – $1000",
        "fact": "Meta's apps reach over 3 billion daily users.",
    },
    {
        "name": "Netflix",
        "ticker": "NFLX",
        "sector": "Streaming",
        "price": 1100,
        "hint": "$500+",
        "fact": "Netflix has over 300 million paid subscribers across 190 countries.",
    },
    {
        "name": "Google",
        "ticker": "GOOGL",
        "sector": "Technology",
        "price": 170,
        "hint": "$100 – $500",
        "fact": "Google processes over 8.5 billion searches per day.",
    },
    {
        "name": "Palantir",
        "ticker": "PLTR",
        "sector": "AI / Defense",
        "price": 120,
        "hint": "Under $200",
        "fact": "Palantir's AI platform is used by the US Army and dozens of intelligence agencies.",
    },
    {
        "name": "Spotify",
        "ticker": "SPOT",
        "sector": "Music Streaming",
        "price": 640,
        "hint": "$500 – $1000",
        "fact": "Spotify has over 600 million monthly active users.",
    },
    {
        "name": "AMD",
        "ticker": "AMD",
        "sector": "Semiconductors",
        "price": 110,
        "hint": "Under $200",
        "fact": "AMD's EPYC chips now power a significant share of major cloud data centers.",
    },
    {
        "name": "Coinbase",
        "ticker": "COIN",
        "sector": "Crypto Exchange",
        "price": 240,
        "hint": "$100 – $500",
        "fact": "Coinbase is the largest regulated crypto exchange in the United States.",
    },
]

SECTOR_GOAL_MAP = {
    "Technology":        ["ai", "tech", "growth"],
    "Semiconductors":    ["ai", "tech", "growth"],
    "AI / Defense":      ["ai", "tech"],
    "Streaming":         ["streaming", "entertainment", "growth"],
    "Music Streaming":   ["streaming", "entertainment"],
    "Social Media":      ["tech", "growth", "social"],
    "Electric Vehicles": ["growth", "green", "innovation"],
    "E-Commerce / Cloud":["tech", "growth", "cloud"],
    "Crypto Exchange":   ["crypto", "alternative", "growth"],
}

TIERS = ["S+", "S", "A", "B", "C", "D", "F"]

TIER_STYLES = {
    "S+": "bold green",
    "S":  "green",
    "A":  "bold cyan",
    "B":  "cyan",
    "C":  "bold yellow",
    "D":  "yellow",
    "F":  "bold red",
}
