import sqlite3
import tempfile
from pathlib import Path
import unittest
from sqlite_cutover_inventory import inventory

class CutoverTests(unittest.TestCase):
    def test_empty_fixture_is_eligible_but_operational_data_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"source.sqlite"
            with sqlite3.connect(path) as conn:
                conn.execute("CREATE TABLE properties(slug TEXT)")
                conn.execute("INSERT INTO properties VALUES ('demo-hotel')")
                conn.execute("CREATE TABLE cases(id TEXT)")
                conn.execute("CREATE TABLE public_facts(source TEXT)")
                conn.execute("INSERT INTO public_facts VALUES ('synthetic_demo_fixture')")
            self.assertTrue(inventory(path)["empty_cutover_eligible"])
            with sqlite3.connect(path) as conn:
                conn.execute("INSERT INTO cases VALUES ('existing-case')")
            report=inventory(path)
            self.assertFalse(report["empty_cutover_eligible"])
            self.assertEqual(report["operational_rows"],1)
    def test_missing_file_is_not_created(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"absent.sqlite"
            with self.assertRaises(FileNotFoundError):
                inventory(path)
            self.assertFalse(path.exists())

if __name__=="__main__":
    unittest.main()
