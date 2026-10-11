"""Only these tables in the marked schema are managed by the business CLI."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import JSONB

SCHEMA = "whitebear_business"
SCHEMA_MARKER = "WhiteBearDataAgent managed business schema v1"
LOCK_ID = 872406101
metadata = MetaData(schema=SCHEMA)

customers = Table(
    "customers",
    metadata,
    Column("id", Integer, primary_key=True, comment="客户编号"),
    Column("name", String(100), nullable=False, comment="客户名称"),
    Column("region", String(50), nullable=False, comment="客户所在区域"),
    comment="客户：每行代表一位客户",
)
categories = Table(
    "categories",
    metadata,
    Column("id", Integer, primary_key=True, comment="品类编号"),
    Column("name", String(100), nullable=False, unique=True, comment="品类名称"),
    comment="商品分类",
)
products = Table(
    "products",
    metadata,
    Column("id", Integer, primary_key=True, comment="商品编号"),
    Column("category_id", Integer, ForeignKey(f"{SCHEMA}.categories.id"), nullable=False),
    Column("name", String(100), nullable=False, comment="商品名称"),
    Column("price", Numeric(12, 2), nullable=False, comment="商品标价"),
    CheckConstraint("price > 0"),
    comment="商品及品类归属",
)
orders = Table(
    "orders",
    metadata,
    Column("id", Integer, primary_key=True, comment="订单编号"),
    Column("customer_id", Integer, ForeignKey(f"{SCHEMA}.customers.id"), nullable=False),
    Column("status", String(20), nullable=False, comment="paid 已支付；unpaid 未支付"),
    Column("ordered_at", DateTime(timezone=True), nullable=False, comment="下单时间"),
    Column("paid_at", DateTime(timezone=True), comment="支付时间；销售额按此时间归属"),
    Column("paid_amount", Numeric(12, 2), nullable=False, comment="订单实付金额"),
    CheckConstraint("paid_amount >= 0"),
    CheckConstraint("paid_at IS NULL OR paid_at >= ordered_at"),
    CheckConstraint(
        "(status = 'paid' AND paid_at IS NOT NULL) OR "
        "(status = 'unpaid' AND paid_at IS NULL AND paid_amount = 0)"
    ),
    comment="订单：支付订单数须按订单编号去重",
)
order_items = Table(
    "order_items",
    metadata,
    Column("id", Integer, primary_key=True, comment="订单明细编号"),
    Column("order_id", Integer, ForeignKey(f"{SCHEMA}.orders.id"), nullable=False),
    Column("product_id", Integer, ForeignKey(f"{SCHEMA}.products.id"), nullable=False),
    Column("quantity", Integer, nullable=False, comment="购买数量"),
    Column("unit_price", Numeric(12, 2), nullable=False, comment="下单时商品单价"),
    Column("paid_amount", Numeric(12, 2), nullable=False, comment="明细实付金额（含折扣）"),
    CheckConstraint("quantity > 0 AND unit_price > 0 AND paid_amount >= 0"),
    CheckConstraint("paid_amount <= quantity * unit_price"),
    comment="订单明细：实付销售额在此粒度汇总，避免关联退款后重复计数",
)
refunds = Table(
    "refunds",
    metadata,
    Column("id", Integer, primary_key=True, comment="退款编号"),
    Column("order_item_id", Integer, ForeignKey(f"{SCHEMA}.order_items.id"), nullable=False),
    Column("status", String(20), nullable=False, comment="success 成功；pending 处理中"),
    Column("requested_at", DateTime(timezone=True), nullable=False, comment="申请退款时间"),
    Column("succeeded_at", DateTime(timezone=True), comment="退款成功时间；退款额按此时间归属"),
    Column("amount", Numeric(12, 2), nullable=False, comment="退款金额"),
    CheckConstraint("amount > 0"),
    CheckConstraint("succeeded_at IS NULL OR succeeded_at >= requested_at"),
    CheckConstraint(
        "(status = 'success' AND succeeded_at IS NOT NULL) OR "
        "(status = 'pending' AND succeeded_at IS NULL)"
    ),
    comment="退款：按成功时间汇总成功退款，时间归属与销售额不同",
)
dataset_info = Table(
    "dataset_info",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("summary", JSONB, nullable=False),
    CheckConstraint("id = 1"),
    comment="业务数据生成参数和汇总；不提供给 Agent 分析",
)
BUSINESS_TABLES = (customers, categories, products, orders, order_items, refunds)
