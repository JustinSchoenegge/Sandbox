from datetime import datetime, date

from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import Static, Input
from textual.containers import ScrollableContainer
from rich.text import Text
from rich.console import Group as RichGroup

from portfolio import load_portfolio, calculate_weights, save_portfolio, check_alignment, safe_pnl
from stocks import STOCKS, TIER_STYLES
from context import invalidate_context_cache


class PortfolioScreen(Screen):
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("a", "add_mode", "Add"),
        ("e", "edit_mode", "Edit"),
        ("r", "remove_mode", "Remove"),
        ("g", "goals_mode", "Goals"),
        ("escape", "cancel_input", "Cancel"),
    ]

    _TIERS = ["S+", "S", "A", "B", "C", "D", "F"]

    def compose(self) -> ComposeResult:
        yield Static("[bold white]═══  PORTFOLIO  ═══[/bold white]", classes="sub-title")
        yield Static("", id="port-goals")
        with ScrollableContainer(id="port-rows"):
            yield Static("", id="port-content")
        yield Input(placeholder="", id="port-input", classes="hidden")
        yield Static("", id="port-msg", classes="sub-msg")
        yield Static(
            "[bold #e8a020][[a]][/bold #e8a020][white] add  [/white]"
            "[bold #e8a020][[e]][/bold #e8a020][white] edit  [/white]"
            "[bold #e8a020][[r]][/bold #e8a020][white] remove  [/white]"
            "[bold #e8a020][[g]][/bold #e8a020][white] goals  [/white]"
            "[bold #e8a020][[q]][/bold #e8a020][white] back[/white]",
            classes="sub-hint",
        )

    def on_mount(self) -> None:
        self._mode: str | None = None
        self._pending: dict = {}
        self._edit_idx: int | None = None

    def on_show(self) -> None:
        self._populate_table()

    def _populate_table(self) -> None:
        try:
            portfolio = load_portfolio()
            goals = portfolio.get("goals", [])
            goals_str = "  ·  ".join(goals) if goals else "no goals — press [g] to add"
            try:
                self.query_one("#port-goals", Static).update(
                    Text(f"Goals: {goals_str}", style="dim #4a9eff")
                )
            except Exception:
                pass

            holdings = portfolio.get("holdings", [])
            msg = self.query_one("#port-msg", Static)
            content_w = self.query_one("#port-content", Static)

            if not holdings:
                content_w.update(Text("No positions yet — press [a] to add one.", style="dim #2a3a5a"))
                msg.update(Text(""))
                return

            rows = calculate_weights(holdings)
            total = sum(r["value"] for r in rows)

            bar_width = max(20, (self.size.width or 110) - 12)

            blocks: list[Text] = []
            for i, r in enumerate(rows, 1):
                w = r["weight"]
                pnl_pct = safe_pnl(r["current_price"], r["avg_cost"])
                up = pnl_pct >= 0
                tier = r.get("tier", "?")
                tier_style = TIER_STYLES.get(tier, "white")
                al_label, _ = check_alignment(r.get("sector", ""), goals)
                if "Strong" in al_label:
                    dot, dot_style = "●", "bold #00c040"
                elif "Partial" in al_label:
                    dot, dot_style = "◑", "bold #e8a020"
                else:
                    dot, dot_style = "○", "dim #c03040"

                direction = r.get("direction", "long")
                dir_label = "L" if direction == "long" else "S"
                dir_style = "#4a9eff" if direction == "long" else "#e8a020"
                opened_str = r.get("opened_date", "")
                days_held = None
                if opened_str:
                    try:
                        opened = date.fromisoformat(opened_str)
                        days_held = (date.today() - opened).days
                    except ValueError:
                        pass
                age_str = f"{days_held}d" if days_held is not None else "?"
                t = Text()
                t.append(f"  {r['ticker']:<6}", style="bold white")
                name = r.get("name", r["ticker"])[:20]
                t.append(f"{name:<22}", style="dim #5f87af")
                sector = r.get("sector", "?")[:10]
                t.append(f"{sector:<12}", style="dim #4a5568")
                t.append(f"{tier:<5}", style=tier_style)
                t.append(f"[{dir_label}]", style=f"bold {dir_style}")
                t.append(f" {age_str:<6}", style="dim #4a5568")
                t.append(f"{pnl_pct:+.1f}%{'↑' if up else '↓'}",
                         style="bold #00c040" if up else "bold #c03040")
                t.append("  ")
                t.append(dot, style=dot_style)

                pct_str = f" {w * 100:.1f}%"
                bar_usable = bar_width - len(pct_str)
                filled = max(1, round(w * bar_usable))
                empty = bar_usable - filled
                t.append("\n  ")
                t.append("▓" * filled, style="#1a4a7a")
                t.append("░" * empty, style="#091520")
                t.append(pct_str, style="bold #4a9eff")

                blocks.append(t)

            content_w.update(RichGroup(*[b for block in blocks for b in (block, Text(""))]))
            msg.update(Text(f"${total:,.2f} total  ·  {len(rows)} position{'s' if len(rows) != 1 else ''}",
                            style="dim #5f87af"))
        except Exception:
            try:
                self.query_one("#port-msg", Static).update(Text("Portfolio unavailable.", style="dim"))
            except Exception:
                pass

    def _set_input(self, placeholder: str) -> None:
        inp = self.query_one("#port-input", Input)
        inp.placeholder = placeholder
        inp.value = ""
        inp.remove_class("hidden")
        inp.focus()

    def action_add_mode(self) -> None:
        self._mode = "ticker"
        self._pending = {}
        self._set_input("Ticker (e.g. AAPL)…")

    def action_edit_mode(self) -> None:
        self._mode = "edit_ticker"
        self._edit_idx = None
        self._set_input("Ticker to edit (e.g. AAPL)…")

    def action_remove_mode(self) -> None:
        self._mode = "remove"
        self._set_input("Ticker to remove (e.g. AAPL)…")

    def action_goals_mode(self) -> None:
        self._mode = "goals"
        self._set_input("Goals (comma separated)…")

    def action_cancel_input(self) -> None:
        self._mode = None
        self._pending = {}
        self._edit_idx = None
        inp = self.query_one("#port-input", Input)
        inp.add_class("hidden")
        inp.value = ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        msg = self.query_one("#port-msg", Static)

        if self._mode == "goals":
            if value:
                try:
                    portfolio = load_portfolio()
                    portfolio["goals"] = [g.strip() for g in value.split(",") if g.strip()]
                    save_portfolio(portfolio)
                    invalidate_context_cache()
                    msg.update(Text("Goals updated.", style="bold #00c040"))
                except Exception:
                    msg.update(Text("Error saving goals.", style="bold #c03040"))
            self.action_cancel_input()
            self._populate_table()
            return

        if self._mode == "remove":
            ticker = value.upper()
            try:
                portfolio = load_portfolio()
                holdings = portfolio["holdings"]
                idx = next((i for i, h in enumerate(holdings) if h["ticker"] == ticker), None)
                if idx is not None:
                    removed = holdings.pop(idx)
                    save_portfolio(portfolio)
                    invalidate_context_cache()
                    msg.update(Text(f"{removed['ticker']} removed.", style="bold #00c040"))
                else:
                    names = "  ".join(h["ticker"] for h in holdings)
                    msg.update(Text(f"Not found. Holdings: {names}", style="bold #c03040"))
            except Exception:
                msg.update(Text("Error removing position.", style="bold #c03040"))
            self.action_cancel_input()
            self._populate_table()
            return

        if self._mode == "edit_ticker":
            ticker = value.upper()
            try:
                portfolio = load_portfolio()
                holdings = portfolio["holdings"]
                idx = next((i for i, h in enumerate(holdings) if h["ticker"] == ticker), None)
                if idx is not None:
                    self._edit_idx = idx
                    h = holdings[idx]
                    msg.update(Text(
                        f"{h['ticker']}: shares={h['shares']}  cost={h['avg_cost']}  tier={h.get('tier','?')}"
                        f"  dir={h.get('direction','long')}  opened={h.get('opened_date','?')}",
                        style="dim #5f87af",
                    ))
                    self._mode = "edit_field"
                    self._set_input("Field: shares / cost / tier / dir / date")
                else:
                    names = "  ".join(h["ticker"] for h in holdings)
                    msg.update(Text(f"Not found. Holdings: {names}", style="bold #c03040"))
            except Exception:
                msg.update(Text("Error.", style="bold #c03040"))
            return

        if self._mode == "edit_field":
            field = value.lower()
            if field not in ("shares", "cost", "tier", "dir", "date"):
                msg.update(Text("Enter: shares, cost, tier, dir, or date", style="bold #c03040"))
                return
            self._mode = f"edit_{field}"
            prompts = {
                "shares": "New shares…",
                "cost": "New avg cost ($)…",
                "tier": f"New tier ({'/'.join(self._TIERS)})…",
                "dir": "New direction (long / short)…",
                "date": "New opened date (YYYY-MM-DD)…",
            }
            self._set_input(prompts[field])
            return

        if self._mode in ("edit_shares", "edit_cost"):
            try:
                float(value)
            except ValueError:
                msg.update(Text("Enter a number.", style="bold #c03040"))
                return
            try:
                portfolio = load_portfolio()
                key = "shares" if self._mode == "edit_shares" else "avg_cost"
                portfolio["holdings"][self._edit_idx][key] = float(value)
                save_portfolio(portfolio)
                invalidate_context_cache()
                msg.update(Text("Position updated.", style="bold #00c040"))
            except Exception:
                msg.update(Text("Error updating.", style="bold #c03040"))
            self.action_cancel_input()
            self._populate_table()
            return

        if self._mode == "edit_tier":
            tier = value.upper()
            if tier not in self._TIERS:
                msg.update(Text(f"Tier must be one of: {', '.join(self._TIERS)}", style="bold #c03040"))
                return
            try:
                portfolio = load_portfolio()
                portfolio["holdings"][self._edit_idx]["tier"] = tier
                save_portfolio(portfolio)
                invalidate_context_cache()
                msg.update(Text("Tier updated.", style="bold #00c040"))
            except Exception:
                msg.update(Text("Error updating.", style="bold #c03040"))
            self.action_cancel_input()
            self._populate_table()
            return

        if self._mode == "edit_dir":
            direction = value.lower()
            if direction not in ("long", "short"):
                msg.update(Text("Enter 'long' or 'short'.", style="bold #c03040"))
                return
            try:
                portfolio = load_portfolio()
                portfolio["holdings"][self._edit_idx]["direction"] = direction
                save_portfolio(portfolio)
                invalidate_context_cache()
                msg.update(Text("Direction updated.", style="bold #00c040"))
            except Exception:
                msg.update(Text("Error updating.", style="bold #c03040"))
            self.action_cancel_input()
            self._populate_table()
            return

        if self._mode == "edit_date":
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                msg.update(Text("Use YYYY-MM-DD format.", style="bold #c03040"))
                return
            try:
                portfolio = load_portfolio()
                portfolio["holdings"][self._edit_idx]["opened_date"] = value
                save_portfolio(portfolio)
                invalidate_context_cache()
                msg.update(Text("Date updated.", style="bold #00c040"))
            except Exception:
                msg.update(Text("Error updating.", style="bold #c03040"))
            self.action_cancel_input()
            self._populate_table()
            return

        if self._mode == "ticker":
            if not value:
                msg.update(Text("Ticker cannot be empty.", style="bold #c03040"))
                return
            ticker = value.upper()
            self._pending["ticker"] = ticker
            known = next((s for s in STOCKS if s["ticker"] == ticker), None)
            if known:
                self._pending["sector"] = known["sector"]
                self._pending["name"] = known["name"]
            else:
                self._pending["sector"] = "Unknown"
                self._pending["name"] = ticker
            self._mode = "shares"
            self._set_input("Shares owned…")

        elif self._mode == "shares":
            try:
                float(value)
            except ValueError:
                msg.update(Text("Enter a number for shares.", style="bold #c03040"))
                return
            self._pending["shares"] = float(value)
            self._mode = "cost"
            self._set_input("Avg cost per share ($)…")

        elif self._mode == "cost":
            try:
                cost = float(value)
                if cost <= 0:
                    raise ValueError
            except ValueError:
                msg.update(Text("Enter a cost greater than 0.", style="bold #c03040"))
                return
            self._pending["avg_cost"] = cost
            self._mode = "tier"
            tiers = "/".join(self._TIERS)
            self._set_input(f"Tier ({tiers})…")

        elif self._mode == "tier":
            tier = value.upper()
            if tier not in self._TIERS:
                msg.update(Text(f"Tier must be one of: {', '.join(self._TIERS)}", style="bold #c03040"))
                return
            self._pending["tier"] = tier
            self._mode = "direction"
            self._set_input("Direction (long / short)…")

        elif self._mode == "direction":
            direction = value.lower()
            if direction not in ("long", "short"):
                msg.update(Text("Enter 'long' or 'short'.", style="bold #c03040"))
                return
            self._pending["direction"] = direction
            self._mode = "opened_date"
            self._set_input("Date opened (YYYY-MM-DD, or blank for today)…")

        elif self._mode == "opened_date":
            if value:
                try:
                    datetime.strptime(value, "%Y-%m-%d")
                except ValueError:
                    msg.update(Text("Use YYYY-MM-DD format.", style="bold #c03040"))
                    return
                self._pending["opened_date"] = value
            else:
                self._pending["opened_date"] = datetime.now().strftime("%Y-%m-%d")
            try:
                portfolio = load_portfolio()
                ticker = self._pending["ticker"]
                portfolio["holdings"].append({
                    "ticker": ticker,
                    "name": self._pending.get("name", ticker),
                    "sector": self._pending.get("sector", "Unknown"),
                    "shares": self._pending["shares"],
                    "avg_cost": self._pending["avg_cost"],
                    "tier": self._pending["tier"],
                    "direction": self._pending["direction"],
                    "opened_date": self._pending["opened_date"],
                })
                save_portfolio(portfolio)
                invalidate_context_cache()
                msg.update(Text(f"{ticker} added.", style="bold #00c040"))
            except Exception:
                msg.update(Text("Error saving position.", style="bold #c03040"))
            self.action_cancel_input()
            self._populate_table()
