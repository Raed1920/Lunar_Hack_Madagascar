from uuid import UUID

from ..database import fetch_all


class MarketSignalsRepository:
    def list_signals(
        self,
        workspace_id: UUID,
        region: str | None = None,
        signal_type: str | None = None,
        limit: int = 30,
    ) -> list[dict]:
        filters = ["workspace_id = %s", "(expires_at IS NULL OR expires_at > NOW())"]
        params: list = [str(workspace_id)]

        if region:
            filters.append("region = %s")
            params.append(region)

        if signal_type:
            filters.append("signal_type = %s")
            params.append(signal_type)

        params.append(limit)

        query = f"""
            SELECT id, region, source, signal_type, signal_key, signal_value, confidence, tags, fetched_at, expires_at
            FROM market_signals
            WHERE {' AND '.join(filters)}
            ORDER BY fetched_at DESC
            LIMIT %s
        """

        return fetch_all(query, params)
