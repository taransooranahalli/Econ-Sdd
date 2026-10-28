"""Small explicit ISO 4217 subset; currency selection is not FX conversion."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class Currency:
    code: str
    name: str
    symbol: str
    minor_digits: int


CURRENCIES = MappingProxyType({currency.code: currency for currency in (
    Currency("USD", "US Dollar", "$", 2),
    Currency("EUR", "Euro", "€", 2),
    Currency("GBP", "British Pound", "£", 2),
    Currency("CAD", "Canadian Dollar", "CA$", 2),
    Currency("AUD", "Australian Dollar", "A$", 2),
    Currency("INR", "Indian Rupee", "₹", 2),
    Currency("JPY", "Japanese Yen", "¥", 0),
    Currency("KWD", "Kuwaiti Dinar", "KWD ", 3),
)})
DEFAULT_CURRENCY = "USD"
