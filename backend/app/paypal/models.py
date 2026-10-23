"""Pydantic schemas and typed models for PayPal requests and responses."""
from typing import Any, Iterator, Optional
from pydantic import BaseModel, ConfigDict, Field


class OAuthTokenResponse(BaseModel):
    """Response payload returned by PayPal OAuth2 token endpoint."""
    model_config = ConfigDict(extra="ignore")

    access_token: str
    token_type: str = "Bearer"
    app_id: Optional[str] = None
    expires_in: int
    scope: Optional[str] = None
    nonce: Optional[str] = None


class PayoutItemAmount(BaseModel):
    """Monetary value and currency for a payout item."""
    model_config = ConfigDict(extra="ignore")

    value: str
    currency: str = "USD"


class PayoutItem(BaseModel):
    """Individual item within a payout batch."""
    model_config = ConfigDict(extra="ignore")

    recipient_type: str = "EMAIL"
    amount: PayoutItemAmount
    receiver: str
    note: Optional[str] = None
    sender_item_id: Optional[str] = None


class SenderBatchHeader(BaseModel):
    """Sender batch metadata for payout creation."""
    model_config = ConfigDict(extra="ignore")

    sender_batch_id: str
    email_subject: Optional[str] = "You have received a payout"
    email_message: Optional[str] = None
    recipient_type: Optional[str] = "EMAIL"


class CreatePayoutRequest(BaseModel):
    """Request payload sent to PayPal Payouts API."""
    model_config = ConfigDict(extra="ignore")

    sender_batch_header: SenderBatchHeader
    items: list[PayoutItem]


class PayoutBatchHeader(BaseModel):
    """Header information returned by PayPal Payouts API."""
    model_config = ConfigDict(extra="ignore")

    payout_batch_id: str
    batch_status: str
    time_created: Optional[str] = None
    time_completed: Optional[str] = None
    sender_batch_header: Optional[dict[str, Any]] = None
    amount: Optional[dict[str, Any]] = None
    fees: Optional[dict[str, Any]] = None


class PayoutResponse(BaseModel):
    """Typed result of a payout creation, supporting attribute access and tuple unpacking."""
    model_config = ConfigDict(extra="ignore")

    batch_id: str
    batch_status: str
    batch_header: Optional[PayoutBatchHeader] = None
    links: Optional[list[dict[str, Any]]] = None

    def __iter__(self) -> Iterator[str]:
        """Support tuple unpacking: batch_id, batch_status = await create_payout(...)"""
        yield self.batch_id
        yield self.batch_status

    def __getitem__(self, item: str) -> Any:
        """Support dict-style key access."""
        if item == "batch_id":
            return self.batch_id
        if item == "batch_status":
            return self.batch_status
        raise KeyError(item)


class PayoutBatchDetails(BaseModel):
    """Detailed status and items for a payout batch."""
    model_config = ConfigDict(extra="ignore")

    batch_id: str
    batch_status: str
    time_created: Optional[str] = None
    time_completed: Optional[str] = None
    sender_batch_id: Optional[str] = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    raw_response: Optional[dict[str, Any]] = None

    def __iter__(self) -> Iterator[str]:
        yield self.batch_id
        yield self.batch_status
