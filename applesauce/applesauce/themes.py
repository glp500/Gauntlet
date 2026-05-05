from __future__ import annotations

from .models import AnalysisPlan, ThemeChoice, ThemePreset


THEMES: dict[str, ThemePreset] = {
    "executive": ThemePreset(
        name="executive",
        label="Boardroom Slate",
        palette=["#2563EB", "#38BDF8", "#14B8A6", "#F59E0B", "#94A3B8"],
        chart_palette=["#2563EB", "#38BDF8", "#14B8A6", "#F59E0B", "#94A3B8"],
        background="#F8FAFC",
        foreground="#0F172A",
        accent="#2563EB",
        grid="#DCE7F5",
        table_header_background="#DBEAFE",
        table_header_foreground="#1D4ED8",
        table_cell_background="#FFFFFF",
        table_cell_background_alt="#F8FBFF",
    ),
    "playful": ThemePreset(
        name="playful",
        label="Citrus Pop",
        palette=["#F97316", "#FB923C", "#06B6D4", "#84CC16", "#FDE68A"],
        chart_palette=["#F97316", "#FB923C", "#06B6D4", "#84CC16", "#FDE68A"],
        background="#FFF7ED",
        foreground="#1F2937",
        accent="#F97316",
        grid="#FED7AA",
        table_header_background="#FFEDD5",
        table_header_foreground="#C2410C",
        table_cell_background="#FFFFFF",
        table_cell_background_alt="#FFF7ED",
    ),
    "calm": ThemePreset(
        name="calm",
        label="Harbor Calm",
        palette=["#0E7490", "#38BDF8", "#A7F3D0", "#94A3B8", "#CBD5E1"],
        chart_palette=["#0E7490", "#38BDF8", "#14B8A6", "#94A3B8", "#CBD5E1"],
        background="#F0FDFA",
        foreground="#164E63",
        accent="#0E7490",
        grid="#CFFAFE",
        table_header_background="#CCFBF1",
        table_header_foreground="#0F766E",
        table_cell_background="#FFFFFF",
        table_cell_background_alt="#F0FDFA",
    ),
    "technical": ThemePreset(
        name="technical",
        label="Lab Grid",
        palette=["#38BDF8", "#22C55E", "#06B6D4", "#A3A3A3", "#CBD5E1"],
        chart_palette=["#38BDF8", "#22C55E", "#06B6D4", "#A3A3A3", "#CBD5E1"],
        background="#F9FAFB",
        foreground="#111827",
        accent="#38BDF8",
        grid="#D9E6F2",
        table_header_background="#E0F2FE",
        table_header_foreground="#0369A1",
        table_cell_background="#FFFFFF",
        table_cell_background_alt="#F8FAFC",
    ),
    "editorial": ThemePreset(
        name="editorial",
        label="Ink & Apricot",
        palette=["#D97706", "#F59E0B", "#BE123C", "#78716C", "#D6D3D1"],
        chart_palette=["#D97706", "#F59E0B", "#BE123C", "#78716C", "#D6D3D1"],
        background="#FAF7F0",
        foreground="#27272A",
        accent="#D97706",
        grid="#E7E0D4",
        table_header_background="#FEF3C7",
        table_header_foreground="#B45309",
        table_cell_background="#FFFDF9",
        table_cell_background_alt="#FAF7F0",
    ),
}


def choose_theme(plan: AnalysisPlan) -> ThemeChoice:
    name = plan.tone if plan.tone in THEMES else "executive"
    return ThemeChoice(name=name, reason=f"Selected to match the analysis tone: {plan.tone}.")


def get_theme(choice: ThemeChoice) -> ThemePreset:
    return THEMES[choice.name]
