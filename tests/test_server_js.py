import pathlib, shutil, subprocess, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


class ServerActions(unittest.TestCase):
    def test_node_server_action_tests_pass(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "node is required to test src/server.js")
        run = subprocess.run([node, "--test", str(ROOT / "tests/server.test.js")], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
