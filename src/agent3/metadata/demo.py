from agent3.metadata.in_memory import InMemoryMetadataProvider
from agent3.metadata.models import ColumnMetadata, TableMetadata


def build_demo_metadata() -> InMemoryMetadataProvider:
    return InMemoryMetadataProvider((
        TableMetadata(
            full_name="dw.dwd_loan_snapshot",
            description="贷款余额日快照",
            aliases=("贷款快照", "loan balance"),
            partition_fields=("dt",),
            columns=(
                ColumnMetadata("dt", "string", "数据日期"),
                ColumnMetadata("org_id", "string", "机构编号"),
                ColumnMetadata("region_code", "string", "地区代码"),
                ColumnMetadata("product_id", "string", "产品编号"),
                ColumnMetadata("balance_amt", "decimal(20,2)", "贷款余额"),
                ColumnMetadata("status", "string", "贷款状态"),
            ),
        ),
        TableMetadata(
            full_name="dw.dim_org",
            description="机构维表",
            aliases=("机构",),
            columns=(
                ColumnMetadata("org_id", "string", "机构编号"),
                ColumnMetadata("org_name", "string", "机构名称"),
                ColumnMetadata("region_code", "string", "地区代码"),
            ),
        ),
    ))
