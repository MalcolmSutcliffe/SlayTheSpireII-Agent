"""Quick runs by default: the tests that took a second or more are marked `slow` and skipped (see pytest.ini); run them with `pytest -m slow` (or `-m ""` for everything).

The list is by "file::test name" and came from `pytest --durations=0 --durations-min=1.0`; add a test here, or give it `@pytest.mark.slow`, when it turns out to be heavy."""
import pytest

SLOW = {
    "test_deck_eval.py::test_chooser_returns_one_of_the_options_and_skips_a_useless_card",
    "test_deck_eval.py::test_early_floor_applies_to_the_first_three_rewards_of_a_run",
    "test_deck_eval.py::test_pilot_sets_the_fight_count_and_big_decisions_get_the_longer_budget",
    "test_exploration.py::test_a_fight_that_cannot_be_won_keeps_a_small_scale",
    "test_exploration.py::test_the_range_is_the_rollout_rewards_not_the_information_bonus",
    "test_info_bonus.py::test_default_search_is_unchanged",
    "test_info_bonus.py::test_half_an_hp_adds_at_most_half_an_hp_of_reward_to_the_draw",
    "test_info_bonus.py::test_the_outcomes_own_values_stay_free_of_the_bonus",
    "test_map.py::test_columns_and_the_grid_agree",
    "test_map.py::test_every_path_runs_the_whole_height",
    "test_map.py::test_most_maps_get_every_type_they_asked_for",
    "test_map.py::test_paths_never_cross",
    "test_map.py::test_placement_rules",
    "test_map.py::test_rows_and_edges_of_the_map",
    "test_map.py::test_the_fast_segment_search_finds_what_the_game_search_finds",
    "test_map.py::test_the_fixed_rows",
    "test_map.py::test_type_totals_do_not_exceed_what_was_asked_for",
    "test_mcts.py::test_a_longer_budget_allows_more_sims",
    "test_mcts.py::test_agent_wins_the_narrow_race[0]",
    "test_mcts.py::test_agent_wins_the_narrow_race[1]",
    "test_mcts.py::test_agent_wins_the_narrow_race[2]",
    "test_mcts.py::test_an_exhausted_time_budget_still_runs_the_minimum_sims[0]",
    "test_mcts.py::test_an_exhausted_time_budget_still_runs_the_minimum_sims[1e-09]",
    "test_mcts.py::test_an_expired_time_budget_is_reported",
    "test_mcts.py::test_chance_node_visits_equal_the_sum_of_its_outcomes",
    "test_mcts.py::test_deterministic_node_visits_cover_their_children",
    "test_mcts.py::test_disabling_early_exit_runs_to_the_sim_cap",
    "test_mcts.py::test_every_simulation_reaches_the_root",
    "test_mcts.py::test_outcome_count_stays_under_the_cap_throughout_the_tree",
    "test_mcts.py::test_search_does_not_modify_the_input_state",
    "test_mcts.py::test_search_is_reproducible_from_a_seed",
    "test_mcts.py::test_search_returns_root_stats_and_exit_reason",
    "test_mcts.py::test_search_terminates_on_a_stalled_fight",
    "test_mcts.py::test_search_with_draws_returns_a_legal_action",
    "test_mcts.py::test_statistical_exit_stops_the_search_when_enabled",
    "test_mcts.py::test_time_budget_ends_the_search_before_the_sim_cap",
    "test_mcts.py::test_tree_contains_both_node_types",
    "test_order.py::test_a_search_reports_the_order_check_and_the_switch_turns_it_off",
    "test_paired.py::test_the_full_search_picks_the_better_block_and_reports_it",
    "test_reuse.py::test_a_chain_of_reuses_survives_transposed_children",
    "test_reuse.py::test_a_draw_outcome_that_was_not_sampled_starts_a_fresh_tree",
    "test_reuse.py::test_a_fresh_tree_gets_a_new_reward_scale",
    "test_reuse.py::test_a_sampled_draw_outcome_is_reused",
    "test_reuse.py::test_a_state_the_search_never_reached_starts_a_fresh_tree",
    "test_reuse.py::test_actions_are_indexed_for_the_observed_state_not_the_old_one",
    "test_reuse.py::test_children_visits_cover_the_root_after_reuse",
    "test_reuse.py::test_every_kept_node_hangs_below_the_new_root",
    "test_reuse.py::test_first_search_is_not_a_reuse",
    "test_reuse.py::test_new_simulations_are_counted_without_the_inherited_ones",
    "test_reuse.py::test_next_search_continues_from_the_node_the_move_led_to",
    "test_reuse.py::test_reuse_can_be_switched_off",
    "test_reuse.py::test_reused_search_still_takes_the_kill",
    "test_reuse.py::test_searching_the_same_state_again_keeps_what_was_learned",
    "test_reuse.py::test_statistics_follow_the_card_when_the_hand_is_reordered",
    "test_reuse.py::test_the_first_searchs_reward_scale_is_kept",
    "test_reuse.py::test_the_old_tree_is_released",
    "test_reuse.py::test_the_table_holds_only_kept_non_root_child_nodes_under_their_own_key",
    "test_sandbox.py::test_relics_are_drawn_from_the_bag_and_never_repeat",
    "test_tiebreak.py::test_a_tie_break_move_is_always_one_of_the_roots_children",
    "test_transposition.py::test_a_search_with_draws_still_runs_and_is_reproducible",
    "test_transposition.py::test_each_search_starts_with_an_empty_table",
    "test_transposition.py::test_root_children_visits_are_their_own",
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        if f"{item.path.name}::{item.name}" in SLOW:
            item.add_marker(pytest.mark.slow)


try:
    import xdist  # noqa: F401
except ImportError:
    pass
else:
    def pytest_xdist_auto_num_workers(config):
        """`-n auto` leaves two cores (and uses at most 6 workers) for the desktop: a worker per core, each running a CPU-bound search, froze the machine. `-n 3` and the like still mean what they say."""
        import os
        return max(1, min(6, (os.cpu_count() or 2) - 2))
