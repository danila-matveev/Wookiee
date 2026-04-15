"""Tests for cabinet_name filter in sku_mapping.py queries."""

import unittest
from unittest.mock import MagicMock, patch


class TestGetArtikulyStatuses(unittest.TestCase):
    """Tests for get_artikuly_statuses cabinet_name filter."""

    def _make_mock_conn(self, rows):
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = rows
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        return mock_conn, mock_cur

    @patch("shared.data_layer.sku_mapping.psycopg2.connect")
    def test_no_cabinet_no_where(self, mock_connect):
        """Without cabinet_name — no WHERE/importery in query."""
        mock_conn, mock_cur = self._make_mock_conn([("vuki/black", "Продается", "Vuki")])
        mock_connect.return_value = mock_conn

        from shared.data_layer.sku_mapping import get_artikuly_statuses
        get_artikuly_statuses()

        args, _ = mock_cur.execute.call_args
        query = args[0]
        params = args[1] if len(args) > 1 else ()
        self.assertNotIn("importery", query.lower())
        self.assertNotIn("WHERE", query)
        self.assertEqual(params, ())

    @patch("shared.data_layer.sku_mapping.psycopg2.connect")
    def test_cabinet_ip_joins_importery(self, mock_connect):
        """With cabinet_name='ИП' — query includes importery join and WHERE."""
        mock_conn, mock_cur = self._make_mock_conn([("vuki/black", "Продается", "Vuki")])
        mock_connect.return_value = mock_conn

        from shared.data_layer.sku_mapping import get_artikuly_statuses
        get_artikuly_statuses(cabinet_name="ИП")

        args, _ = mock_cur.execute.call_args
        query = args[0]
        params = args[1] if len(args) > 1 else ()
        self.assertIn("importery", query.lower())
        self.assertIn("WHERE", query)
        self.assertIn("%ИП%", params)

    @patch("shared.data_layer.sku_mapping.psycopg2.connect")
    def test_cabinet_ooo_joins_importery(self, mock_connect):
        """With cabinet_name='ООО' — query includes importery join and WHERE."""
        mock_conn, mock_cur = self._make_mock_conn([])
        mock_connect.return_value = mock_conn

        from shared.data_layer.sku_mapping import get_artikuly_statuses
        get_artikuly_statuses(cabinet_name="ООО")

        args, _ = mock_cur.execute.call_args
        query = args[0]
        params = args[1] if len(args) > 1 else ()
        self.assertIn("importery", query.lower())
        self.assertIn("%ООО%", params)


class TestGetArtikul_ToSubmodelMapping(unittest.TestCase):
    """Tests for get_artikul_to_submodel_mapping cabinet_name filter."""

    def _make_mock_conn(self, rows):
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = rows
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        return mock_conn, mock_cur

    @patch("shared.data_layer.sku_mapping.psycopg2.connect")
    def test_no_cabinet_no_where(self, mock_connect):
        """Without cabinet_name — no importery in query."""
        mock_conn, mock_cur = self._make_mock_conn([("vuki/black", "VukiN", "Vuki")])
        mock_connect.return_value = mock_conn

        from shared.data_layer.sku_mapping import get_artikul_to_submodel_mapping
        get_artikul_to_submodel_mapping()

        args, _ = mock_cur.execute.call_args
        query = args[0]
        params = args[1] if len(args) > 1 else ()
        self.assertNotIn("importery", query.lower())
        self.assertEqual(params, ())

    @patch("shared.data_layer.sku_mapping.psycopg2.connect")
    def test_cabinet_ip_joins_importery(self, mock_connect):
        """With cabinet_name='ИП' — query includes importery join and filter."""
        mock_conn, mock_cur = self._make_mock_conn([("vuki/black", "VukiN", "Vuki")])
        mock_connect.return_value = mock_conn

        from shared.data_layer.sku_mapping import get_artikul_to_submodel_mapping
        get_artikul_to_submodel_mapping(cabinet_name="ИП")

        args, _ = mock_cur.execute.call_args
        query = args[0]
        params = args[1] if len(args) > 1 else ()
        self.assertIn("importery", query.lower())
        self.assertIn("WHERE", query)
        self.assertIn("%ИП%", params)

    @patch("shared.data_layer.sku_mapping.psycopg2.connect")
    def test_cabinet_ooo_joins_importery(self, mock_connect):
        """With cabinet_name='ООО' — query includes importery join and filter."""
        mock_conn, mock_cur = self._make_mock_conn([])
        mock_connect.return_value = mock_conn

        from shared.data_layer.sku_mapping import get_artikul_to_submodel_mapping
        get_artikul_to_submodel_mapping(cabinet_name="ООО")

        args, _ = mock_cur.execute.call_args
        query = args[0]
        params = args[1] if len(args) > 1 else ()
        self.assertIn("importery", query.lower())
        self.assertIn("%ООО%", params)


class TestGetNmToArticleMapping(unittest.TestCase):
    """Tests for get_nm_to_article_mapping cabinet_name filter."""

    def _make_mock_conn(self, rows):
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = rows
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        return mock_conn, mock_cur

    @patch("shared.data_layer.sku_mapping.psycopg2.connect")
    def test_no_cabinet_no_exists(self, mock_connect):
        """Without cabinet_name — no EXISTS/importery in query."""
        mock_conn, mock_cur = self._make_mock_conn([(123456, "vuki/black")])
        mock_connect.return_value = mock_conn

        from shared.data_layer.sku_mapping import get_nm_to_article_mapping
        result = get_nm_to_article_mapping()

        args, _ = mock_cur.execute.call_args
        query = args[0]
        params = args[1] if len(args) > 1 else ()
        self.assertNotIn("importery", query.lower())
        self.assertNotIn("EXISTS", query)
        self.assertEqual(params, ())
        self.assertEqual(result, {123456: "vuki/black"})

    @patch("shared.data_layer.sku_mapping.psycopg2.connect")
    def test_cabinet_ip_adds_exists(self, mock_connect):
        """With cabinet_name='ИП' — query uses EXISTS subquery with importery."""
        mock_conn, mock_cur = self._make_mock_conn([(123456, "vuki/black")])
        mock_connect.return_value = mock_conn

        from shared.data_layer.sku_mapping import get_nm_to_article_mapping
        result = get_nm_to_article_mapping(cabinet_name="ИП")

        args, _ = mock_cur.execute.call_args
        query = args[0]
        params = args[1] if len(args) > 1 else ()
        self.assertIn("EXISTS", query)
        self.assertIn("importery", query.lower())
        self.assertIn("%ИП%", params)

    @patch("shared.data_layer.sku_mapping.psycopg2.connect")
    def test_cabinet_ooo_adds_exists(self, mock_connect):
        """With cabinet_name='ООО' — query uses EXISTS subquery with importery."""
        mock_conn, mock_cur = self._make_mock_conn([])
        mock_connect.return_value = mock_conn

        from shared.data_layer.sku_mapping import get_nm_to_article_mapping
        result = get_nm_to_article_mapping(cabinet_name="ООО")

        args, _ = mock_cur.execute.call_args
        query = args[0]
        params = args[1] if len(args) > 1 else ()
        self.assertIn("importery", query.lower())
        self.assertIn("%ООО%", params)
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
