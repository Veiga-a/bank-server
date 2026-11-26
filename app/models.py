from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Integer,
    Numeric, SmallInteger, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# --------------------------------------------------------------------------- #
# Base
# --------------------------------------------------------------------------- #


def pk_uuid() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=uuid.uuid4)


def created_at_col() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def updated_at_col() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


def enum_col(e: type[enum.Enum], **kw):
    # Stored as VARCHAR + CHECK constraint: easy to migrate, works on any DB.
    return mapped_column(
        Enum(e, native_enum=False, length=20, values_callable=lambda x: [m.value for m in x]),
        **kw,
    )


# --------------------------------------------------------------------------- #
# Enums (replace the small lookup tables)
# --------------------------------------------------------------------------- #
class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"


class AccountType(str, enum.Enum):
    USER = "user"        # belongs to a customer
    SYSTEM = "system"    # owned by the bank: EXTERNAL_EUR, FX_EUR, FEES_EUR...


class AccountStatus(str, enum.Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


class TransactionType(str, enum.Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    CONVERSION = "conversion"
    FEE = "fee"
    REVERSAL = "reversal"


class TransactionStatus(str, enum.Enum):
    PENDING = "pending"      # created, not yet in the ledger
    POSTED = "posted"        # ledger entries written, balances changed
    FAILED = "failed"        # rejected (insufficient funds, frozen account...)
    REVERSED = "reversed"    # undone by a later REVERSAL transaction


class PaymentMethod(str, enum.Enum):
    CARD = "card"
    SEPA = "sepa"
    SWIFT = "swift"
    PIX = "pix"


# --------------------------------------------------------------------------- #
# Reference data
# --------------------------------------------------------------------------- #
class Country(Base):
    __tablename__ = "countries"

    iso2: Mapped[str] = mapped_column(String(2), primary_key=True)           # "FR"
    iso3: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)  # "FRA"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_code: Mapped[str] = mapped_column(String(5), nullable=False)        # "+33"
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class Currency(Base):
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)            # "EUR"
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(5), nullable=False)            # "R$"
    minor_units: Mapped[int] = mapped_column(SmallInteger, nullable=False)    # EUR=2, JPY=0
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    __table_args__ = (CheckConstraint("minor_units BETWEEN 0 AND 4", name="ck_currency_minor_units"),)


class ExchangeRate(Base):
    """1 base = rate * quote. A row is valid from effective_from until effective_to (NULL = current)."""
    __tablename__ = "exchange_rates"

    id: Mapped[uuid.UUID] = pk_uuid()
    base_currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    quote_currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)           # "ECB", "manual"...
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint("base_currency", "quote_currency", "effective_from", name="uq_rate_pair_from"),
        CheckConstraint("base_currency <> quote_currency", name="ck_rate_distinct_pair"),
        CheckConstraint("rate > 0", name="ck_rate_positive"),
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="ck_rate_period"),
    )


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = pk_uuid()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(20))
    country_code: Mapped[str] = mapped_column(ForeignKey("countries.iso2"), nullable=False)
    address_line: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    role: Mapped[UserRole] = enum_col(UserRole, default=UserRole.CUSTOMER, nullable=False)
    status: Mapped[UserStatus] = enum_col(UserStatus, default=UserStatus.ACTIVE, nullable=False)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    accounts: Mapped[list[Account]] = relationship(back_populates="user")
    beneficiaries: Mapped[list[Beneficiary]] = relationship(back_populates="user")


class Beneficiary(Base):
    """External bank account a user can withdraw to (replaces accounts.bank_details)."""
    __tablename__ = "beneficiaries"

    id: Mapped[uuid.UUID] = pk_uuid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    country_code: Mapped[str] = mapped_column(ForeignKey("countries.iso2"), nullable=False)
    holder_name: Mapped[str] = mapped_column(String(200), nullable=False)
    iban: Mapped[str] = mapped_column(String(34), nullable=False)
    bic: Mapped[str | None] = mapped_column(String(11))
    created_at: Mapped[datetime] = created_at_col()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # soft delete

    user: Mapped[User] = relationship(back_populates="beneficiaries")


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #
class Account(Base):
    """One account = one currency. A user with EUR and BRL has two accounts."""
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = pk_uuid()
    account_type: Mapped[AccountType] = enum_col(AccountType, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    system_code: Mapped[str | None] = mapped_column(String(30), unique=True)  # "FX_EUR"
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)  # minor units, CACHE
    status: Mapped[AccountStatus] = enum_col(AccountStatus, default=AccountStatus.ACTIVE, nullable=False)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User | None] = relationship(back_populates="accounts")
    entries: Mapped[list[LedgerEntry]] = relationship(back_populates="account")

    __table_args__ = (
        # one account per currency per user
        UniqueConstraint("user_id", "currency_code", name="uq_account_user_currency"),
        # user accounts have an owner, system accounts have a code
        CheckConstraint(
            "(account_type = 'user' AND user_id IS NOT NULL AND system_code IS NULL) OR "
            "(account_type = 'system' AND user_id IS NULL AND system_code IS NOT NULL)",
            name="ck_account_owner",
        ),
        # customers can't go negative; system accounts can (e.g. EXTERNAL mirrors money in)
        CheckConstraint("account_type = 'system' OR balance >= 0", name="ck_account_no_overdraft"),
    )


# --------------------------------------------------------------------------- #
# Transactions + ledger
# --------------------------------------------------------------------------- #
class Transaction(Base):
    """Header of a money movement. Amounts live in ledger_entries, not here."""
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = pk_uuid()
    type: Mapped[TransactionType] = enum_col(TransactionType, nullable=False)
    status: Mapped[TransactionStatus] = enum_col(
        TransactionStatus, default=TransactionStatus.PENDING, nullable=False
    )
    initiated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)

    # Idempotency: same (user, key) => same transaction, never executed twice
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # sha256 of request body

    reference: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)  # "TX-2026-000123"
    description: Mapped[str | None] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(String(255))
    reverses_transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transactions.id"))

    created_at: Mapped[datetime] = created_at_col()
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = updated_at_col()

    entries: Mapped[list[LedgerEntry]] = relationship(back_populates="transaction")
    deposit: Mapped[DepositDetails | None] = relationship(back_populates="transaction")
    withdrawal: Mapped[WithdrawalDetails | None] = relationship(back_populates="transaction")
    transfer: Mapped[TransferDetails | None] = relationship(back_populates="transaction")
    conversion: Mapped[ConversionDetails | None] = relationship(back_populates="transaction")

    __table_args__ = (
        UniqueConstraint("initiated_by_user_id", "idempotency_key", name="uq_tx_idempotency"),
        CheckConstraint(
            "(status = 'posted') = (posted_at IS NOT NULL) OR status = 'reversed'",
            name="ck_tx_posted_at",
        ),
    )


class LedgerEntry(Base):
    """One line of the ledger. +amount = credit (money in), -amount = debit (money out).
    Append-only: never UPDATE or DELETE these rows."""
    __tablename__ = "ledger_entries"

    # BIGSERIAL on Postgres (Integer variant only so tests can run on SQLite)
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )  # gives order
    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id"), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)           # minor units, signed
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)    # running balance
    created_at: Mapped[datetime] = created_at_col()

    transaction: Mapped[Transaction] = relationship(back_populates="entries")
    account: Mapped[Account] = relationship(back_populates="entries")

    __table_args__ = (
        CheckConstraint("amount <> 0", name="ck_entry_nonzero"),
        Index("ix_entries_account_id_id", "account_id", "id"),  # fast statements
    )


# --------------------------------------------------------------------------- #
# Detail tables (1:1 with transactions, PK = FK)
# --------------------------------------------------------------------------- #
class DepositDetails(Base):
    __tablename__ = "deposit_details"

    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id"), primary_key=True)
    method: Mapped[PaymentMethod] = enum_col(PaymentMethod, nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(100))  # provider's id

    transaction: Mapped[Transaction] = relationship(back_populates="deposit")


class WithdrawalDetails(Base):
    __tablename__ = "withdrawal_details"

    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id"), primary_key=True)
    beneficiary_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("beneficiaries.id"), nullable=False)
    method: Mapped[PaymentMethod] = enum_col(PaymentMethod, nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(100))

    transaction: Mapped[Transaction] = relationship(back_populates="withdrawal")


class TransferDetails(Base):
    __tablename__ = "transfer_details"

    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id"), primary_key=True)
    source_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    destination_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(String(140))

    transaction: Mapped[Transaction] = relationship(back_populates="transfer")

    __table_args__ = (
        CheckConstraint("source_account_id <> destination_account_id", name="ck_transfer_distinct"),
    )


class ConversionDetails(Base):
    """Snapshot of the FX quote used. Amounts here are informative; the ledger is the truth."""
    __tablename__ = "conversion_details"

    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id"), primary_key=True)
    exchange_rate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exchange_rates.id"), nullable=False)
    source_currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    target_currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    source_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    applied_rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)  # rate incl. spread
    fee_amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)  # in source currency

    transaction: Mapped[Transaction] = relationship(back_populates="conversion")

    __table_args__ = (
        CheckConstraint("source_currency <> target_currency", name="ck_conv_distinct"),
        CheckConstraint("source_amount > 0 AND target_amount > 0 AND fee_amount >= 0", name="ck_conv_amounts"),
    )