"""DCF model constants and fallback values for market data."""

DEFAULT_BETA: float = 1.0
TERMINAL_GROWTH_RATE: float = 0.025   # kept for backward-compat; not used in P/E-exit model
PROJECTION_YEARS: int = 5
ACTUALS_YEARS: int = 5                 # historical years fetched from FMP
MIN_GROWTH_RATE: float = 0.03
TAX_RATE: float = 0.21                 # fallback statutory rate
DEFAULT_EXIT_PE: float = 20.0          # default P/E exit multiple for terminal value
FALLBACK_RISK_FREE_RATE: float = 0.043
FALLBACK_ERP: float = 0.055
