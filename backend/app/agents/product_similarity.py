"""Product similarity via NearestNeighbors on demand profiles."""

from __future__ import annotations

import numpy as np
from sklearn.neighbors import NearestNeighbors

from app.agents.base import BaseAgent, TrainContext


class ProductSimilarityAgent(BaseAgent):
    name = "product_similarity"

    def fit(self, ctx: TrainContext) -> dict:
        rows = ctx.conn.execute(
            """
            SELECT product_id, sale_date, units FROM sales ORDER BY product_id, sale_date
            """
        ).fetchall()
        if not rows:
            raise ValueError("No sales for similarity")
        by_pid: dict[int, list[float]] = {}
        for r in rows:
            by_pid.setdefault(int(r["product_id"]), []).append(float(r["units"]))
        self.metadata["product_ids"] = []
        vectors = []
        for pid, units in sorted(by_pid.items()):
            u = np.array(units[-28:], dtype=float)
            if len(u) < 28:
                u = np.pad(u, (28 - len(u), 0))
            mu, sd = u.mean(), u.std() or 1.0
            vectors.append(np.concatenate([[mu, sd], u / (sd + 1e-6)]))
            self.metadata["product_ids"].append(pid)
        x = np.vstack(vectors)
        self.model = NearestNeighbors(n_neighbors=min(6, len(x)), metric="cosine", algorithm="brute")
        self.model.fit(x)
        self.metadata["vectors"] = x.shape[1]
        return {"n_products": float(len(x))}

    def predict_one(self, conn, product_id: int, **kwargs) -> dict:
        pids = self.metadata.get("product_ids", [])
        if product_id not in pids:
            return {"product_id": product_id, "neighbors": []}
        idx = pids.index(product_id)
        dists, inds = self.model.kneighbors(self.model._fit_X[idx : idx + 1])  # noqa: SLF001
        neighbors = []
        for d, j in zip(dists[0], inds[0]):
            nid = pids[int(j)]
            if nid == product_id:
                continue
            neighbors.append({"product_id": nid, "distance": float(d)})
            if len(neighbors) >= 5:
                break
        return {"product_id": product_id, "neighbors": neighbors}
