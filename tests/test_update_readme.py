import unittest

from scripts.update_readme import cumulative_hours


class TestDevelopmentTime(unittest.TestCase):
    def test_empty_history_has_no_time(self):
        self.assertEqual(cumulative_hours([]), 0.0)

    def test_sessions_include_elapsed_time_and_overhead(self):
        timestamps = [0, 1800, 10800, 11700]

        self.assertEqual(cumulative_hours(timestamps), 1.75)


if __name__ == "__main__":
    unittest.main()
