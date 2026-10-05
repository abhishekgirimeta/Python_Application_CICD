import json
import tempfile
import unittest
from pathlib import Path

from app import TaskStore, render_page


class TaskStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_file = Path(self.temp_dir.name) / "tasks.json"
        self.store = TaskStore(self.data_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_and_reload_task(self):
        self.store.add("Learn Python")
        loaded_store = TaskStore(self.data_file)

        self.assertEqual(
            loaded_store.tasks,
            [{"id": 1, "title": "Learn Python", "done": False}],
        )

    def test_toggle_and_delete_task(self):
        self.store.add("Finish the app")
        self.store.toggle(1)
        self.assertTrue(self.store.tasks[0]["done"])

        self.store.delete(1)
        self.assertEqual(self.store.tasks, [])

    def test_reject_empty_task(self):
        with self.assertRaises(ValueError):
            self.store.add("  ")

    def test_page_escapes_task_text(self):
        page = render_page([{"id": 1, "title": "<script>", "done": False}])
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script>", page)


if __name__ == "__main__":
    unittest.main()
