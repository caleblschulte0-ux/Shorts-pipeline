from __future__ import annotations

FIXTURES = {
    "money": {
        "slug": "grocery_bill_jump", "archetype": "money", "callback_token": "2019_vs_2026",
        "scenes": [
            {"role": "hook", "narration": "2019 was $680. 2026 is $1,030.", "visual_event": "value_collision_slam", "focus": "2026", "duration": 3.2, "callback_token": "2019_vs_2026"},
            {"role": "setup", "narration": "The same basket started at $680.", "visual_event": "receipt_line_enters", "focus": "2019", "duration": 3.6},
            {"role": "explanation", "narration": "By 2022 it reached $860.", "visual_event": "trend_line_climbs", "focus": "2022", "duration": 3.8},
            {"role": "consequence", "narration": "That is $350 more every year.", "visual_event": "burden_stack_forms", "focus": "$350", "duration": 3.9},
            {"role": "payoff", "narration": "The gap between 2019 and 2026 is the story.", "visual_event": "callback_bridge_returns", "focus": "2026", "duration": 3.5, "callback_token": "2019_vs_2026"},
        ],
    },
    "share": {
        "slug": "market_share_squeeze", "archetype": "share", "callback_token": "share_grid",
        "scenes": [
            {"role": "hook", "narration": "One company controls 72% of the market.", "visual_event": "share_squeeze_collision", "focus": "72%", "duration": 3.0, "callback_token": "share_grid"},
            {"role": "setup", "narration": "Everyone else fits into the remaining 28%.", "visual_event": "waffle_remainder_forms", "focus": "28%", "duration": 3.4},
            {"role": "explanation", "narration": "The leader is more than twice the rest.", "visual_event": "scale_collision", "focus": "72%", "duration": 3.7},
            {"role": "consequence", "narration": "That makes every competitor fight for scraps.", "visual_event": "remaining_cells_squeeze", "focus": "28%", "duration": 3.7},
            {"role": "payoff", "narration": "The opening grid returns with the full imbalance.", "visual_event": "callback_share_grid", "focus": "72%", "duration": 3.3, "callback_token": "share_grid"},
        ],
    },
    "ranking": {
        "slug": "city_growth_race", "archetype": "ranking", "callback_token": "finish_line",
        "scenes": [
            {"role": "hook", "narration": "Austin added 180,000 people and won the race.", "visual_event": "rank_race_finish", "focus": "Austin", "duration": 3.1, "callback_token": "finish_line"},
            {"role": "setup", "narration": "Phoenix followed with 150,000.", "visual_event": "rank_rows_enter", "focus": "Phoenix", "duration": 3.4},
            {"role": "explanation", "narration": "Dallas reached 132,000.", "visual_event": "bars_shove_to_length", "focus": "Dallas", "duration": 3.5},
            {"role": "consequence", "narration": "The winner opened a 30,000-person gap.", "visual_event": "finish_gap_opens", "focus": "30,000", "duration": 3.8},
            {"role": "payoff", "narration": "The finish line returns and reveals the real gap.", "visual_event": "callback_finish_line", "focus": "Austin", "duration": 3.3, "callback_token": "finish_line"},
        ],
    },
    "comparison": {
        "slug": "rent_vs_mortgage", "archetype": "comparison", "callback_token": "two_columns",
        "scenes": [
            {"role": "hook", "narration": "Rent is $1,450. The mortgage is $2,180.", "visual_event": "two_column_collision", "focus": "$2,180", "duration": 3.1, "callback_token": "two_columns"},
            {"role": "setup", "narration": "The monthly difference starts at $730.", "visual_event": "gap_measure_enters", "focus": "$730", "duration": 3.4},
            {"role": "explanation", "narration": "Interest pushes the payment higher.", "visual_event": "column_pressure_rises", "focus": "$2,180", "duration": 3.6},
            {"role": "consequence", "narration": "That gap absorbs almost nine thousand dollars a year.", "visual_event": "annual_burden_stack", "focus": "$8,760", "duration": 3.9},
            {"role": "payoff", "narration": "The original columns return with the yearly cost between them.", "visual_event": "callback_two_columns", "focus": "$730", "duration": 3.4, "callback_token": "two_columns"},
        ],
    },
    "single": {
        "slug": "one_shock_stat", "archetype": "single", "callback_token": "gauge_87",
        "scenes": [
            {"role": "hook", "narration": "Eighty-seven percent happens in one place.", "visual_event": "gauge_slam_87", "focus": "87%", "duration": 2.9, "callback_token": "gauge_87"},
            {"role": "setup", "narration": "The gauge starts near zero.", "visual_event": "dial_winds_up", "focus": "0%", "duration": 3.2},
            {"role": "explanation", "narration": "Then it surges past 50%.", "visual_event": "gauge_crosses_half", "focus": "50%", "duration": 3.4},
            {"role": "consequence", "narration": "The remaining 13% barely has room.", "visual_event": "remainder_squeezes", "focus": "13%", "duration": 3.6},
            {"role": "payoff", "narration": "The opening 87% gauge returns and locks in.", "visual_event": "callback_gauge_87", "focus": "87%", "duration": 3.2, "callback_token": "gauge_87"},
        ],
    },
}
