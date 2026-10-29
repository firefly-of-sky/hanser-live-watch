import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import monitor as m


def post(post_id, published="2026-10-29T01:00:00.000Z"):
    return {"id": post_id, "title": "测试动态", "content": "<p>正文</p>", "post_time": published,
            "pictures": [], "author": {"uid": 1, "nickname": "hanserLIVE", "avatar": "https://example.com/avatar.png"}}


class MonitorTests(unittest.TestCase):
    def baseline(self, path):
        state = {"version": 1, "uid": 1, "started_at": "2026-10-29T00:00:00+00:00", "seen_ids": [100], "notified_ids": []}
        m.save_state(path, state)

    def test_initialization_does_not_send_historical_posts(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            with patch.object(m, "page", return_value=[post(100)]), patch.object(m, "detail", return_value=post(100)), patch.object(m, "send_email") as send:
                m.initialize(path)
                send.assert_not_called()
            self.assertEqual(json.loads(path.read_text())["seen_ids"], [100])
            with self.assertRaises(RuntimeError):
                m.initialize(path)

    def test_smtp_failure_retries_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            self.baseline(path)
            initial = path.read_text()
            with patch.object(m, "config"), patch.object(m, "page", return_value=[post(101), post(100)]), patch.object(m, "detail", side_effect=lambda id: post(id)):
                with patch.object(m, "send_email", side_effect=RuntimeError("mail failed")):
                    with self.assertRaises(RuntimeError):
                        m.monitor(path)
                self.assertEqual(path.read_text(), initial)
                with patch.object(m, "send_email") as send:
                    m.monitor(path)
                    m.monitor(path)
                    send.assert_called_once()
            self.assertEqual(json.loads(path.read_text())["notified_ids"], [101])

    def test_read_failure_does_not_modify_state(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            self.baseline(path)
            initial = path.read_text()
            with patch.object(m, "config"), patch.object(m, "page", side_effect=RuntimeError("site down")):
                with self.assertRaises(RuntimeError):
                    m.monitor(path)
            self.assertEqual(path.read_text(), initial)

    def test_pagination_ignores_pinned_known_item(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            self.baseline(path)
            first = [post(100)] + [post(id) for id in range(130, 111, -1)]
            second = [post(id) for id in range(111, 100, -1)] + [post(100)]
            with patch.object(m, "config"), patch.object(m, "page", side_effect=[first, second]) as get, patch.object(m, "detail", side_effect=lambda id: post(id)), patch.object(m, "send_email") as send:
                m.monitor(path)
            self.assertEqual(get.call_count, 2)
            self.assertEqual([p["id"] for p in send.call_args.args[0]], list(range(101, 131)))

    def test_old_unknown_posts_and_counts_do_not_notify(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            self.baseline(path)
            with patch.object(m, "config"), patch.object(m, "page", return_value=[dict(post(100), likes=999), post(99)]), patch.object(m, "detail", return_value=post(99, "2026-10-28T00:00:00Z")), patch.object(m, "send_email") as send:
                m.monitor(path)
                send.assert_not_called()

    def test_wrong_author_and_missing_configuration_fail(self):
        with patch.object(m, "request_json", return_value={"list": [dict(post(100), author={"uid": 2, "nickname": "other"})]}):
            with self.assertRaises(RuntimeError):
                m.page(1)
        with tempfile.TemporaryDirectory() as temp, patch.dict("os.environ", {}, clear=True):
            path = Path(temp) / "state.json"
            with self.assertRaises(RuntimeError):
                m.monitor(path)
            self.assertFalse(path.exists())

    def test_body_images_exclude_avatar_and_scripts(self):
        item = post(1)
        item["content"] = '<p>正文 &amp; 更多</p><img src="https://example.com/body.png"><script>secret</script>'
        item["pictures"] = ["https://example.com/body.png", {"url": "https://example.com/two.png"}, "javascript:alert(1)"]
        text, images = m.post_body(item)
        self.assertEqual(text, "正文 & 更多")
        self.assertEqual(images, ["https://example.com/body.png", "https://example.com/two.png"])


if __name__ == "__main__":
    unittest.main()
