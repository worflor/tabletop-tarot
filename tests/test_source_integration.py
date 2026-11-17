"""Negative checks for source provenance and the migration's preservation oracle."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build
from verify_source import archive_parity


class SourceIntegration(unittest.TestCase):
    def test_modified_original_is_rejected_before_output_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'engine.py').write_bytes(b'original')
            (root / 'source-lock.json').write_text(json.dumps({'files': {'engine.py': hashlib.sha256(b'original').hexdigest()}}))
            out = root / 'dist'; out.mkdir()
            previous = out / 'Tabletop-Tarot-1.1.0.zip'; previous.write_bytes(b'last good')
            (root / 'engine.py').write_bytes(b'changed')
            with patch.object(build, 'VENDOR', root), self.assertRaisesRegex(ValueError, 'Original source changed'):
                build.build(out_dir=out)
            self.assertEqual(previous.read_bytes(), b'last good')

    def test_comparison_accepts_formatting_but_rejects_runtime_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            old, new = Path(temp) / 'old.zip', Path(temp) / 'new.zip'
            with zipfile.ZipFile(old, 'w') as z:
                z.writestr('data/tag.json', '{"values":["minecraft:air"]}')
                z.writestr('data/tick.mcfunction', 'say hello\r\n')
            with zipfile.ZipFile(new, 'w') as z:
                z.writestr('data/tag.json', '{\n  "values": ["minecraft:air"]\n}\n')
                z.writestr('data/tick.mcfunction', 'say hello\n')
            self.assertEqual(archive_parity(old, new), [])
            with zipfile.ZipFile(new, 'w') as z:
                z.writestr('data/tag.json', '{"values":["minecraft:air"]}')
                z.writestr('data/tick.mcfunction', 'kill @a\n')
            self.assertEqual(archive_parity(old, new), ['1.1.0: changed data/tick.mcfunction'])

    def test_missing_member_is_not_hidden_by_valid_zip_crc(self):
        with tempfile.TemporaryDirectory() as temp:
            old, new = Path(temp) / 'old.zip', Path(temp) / 'new.zip'
            with zipfile.ZipFile(old, 'w') as z:
                z.writestr('pack.mcmeta', '{"pack":{}}')
                z.writestr('data/required.mcfunction', 'say required\n')
            with zipfile.ZipFile(new, 'w') as z:
                z.writestr('pack.mcmeta', '{"pack":{}}')
            self.assertEqual(archive_parity(old, new), ['1.1.0: missing data/required.mcfunction'])


class ArchiveAuthority(unittest.TestCase):
    def test_duplicate_member_is_rejected_even_when_last_bytes_match(self):
        from verify import verify_static
        with tempfile.TemporaryDirectory() as temp:
            reference, ambiguous = Path(temp)/'reference.zip', Path(temp)/'ambiguous.zip'
            with zipfile.ZipFile(reference, 'w') as z:
                z.writestr('data/required.mcfunction', 'say required\n')
            with zipfile.ZipFile(ambiguous, 'w') as z:
                z.writestr('data/required.mcfunction', 'say hidden\n')
                with self.assertWarnsRegex(UserWarning, 'Duplicate name'):
                    z.writestr('data/required.mcfunction', 'say required\n')
            with self.assertRaisesRegex(ValueError, 'Duplicate ZIP member: data/required.mcfunction'):
                archive_parity(reference, ambiguous)
            self.assertEqual(verify_static(ambiguous), ['Archive contains duplicate ZIP members'])
            report=Path(temp)/'receipt.json'
            verifier=Path(__file__).resolve().parents[1]/'tools/verify_source.py'
            result=subprocess.run([sys.executable,str(verifier),'--candidate',str(ambiguous),'--report',str(report)],
                                  capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Duplicate ZIP member',result.stderr)
            self.assertFalse(report.exists(), 'Ambiguous archive received a source-verification receipt')

    def test_changed_archive_invalidates_only_the_old_parity_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); archive=root/'pack.zip'; archive.write_bytes(b'first')
            digest=hashlib.sha256(b'first').hexdigest()
            receipt=root/'source-parity.json'
            receipt.write_text(json.dumps({'candidate_sha256':digest, 'passed':True, 'scope':'old comparison'}))
            untouched=receipt.read_bytes()
            build.invalidate_stale_parity(root, archive)
            self.assertEqual(receipt.read_bytes(), untouched)
            archive.write_bytes(b'next')
            build.invalidate_stale_parity(root, archive)
            stale=json.loads(receipt.read_text())
            self.assertFalse(stale['passed'])
            self.assertTrue(stale['previously_passed'])
            self.assertEqual(stale['candidate_sha256'], digest)
            self.assertEqual(stale['superseded_by_sha256'], hashlib.sha256(b'next').hexdigest())
            build.invalidate_stale_parity(root, archive)
            self.assertTrue(json.loads(receipt.read_text())['previously_passed'])
            for broken in ('{unfinished', '[]'):
                receipt.write_text(broken)
                build.invalidate_stale_parity(root, archive)
                repaired=json.loads(receipt.read_text())
                self.assertFalse(repaired['passed'])
                self.assertTrue(repaired['stale'])



class LiveVerifierAdmission(unittest.TestCase):
    def test_assertions_cannot_be_disabled_into_a_false_pass(self):
        runner=Path(__file__).resolve().parent/'test_live.py'
        accepted=subprocess.run([sys.executable,str(runner),'--help'],capture_output=True,text=True)
        self.assertEqual(accepted.returncode,0,accepted.stderr)
        rejected=subprocess.run([sys.executable,'-O',str(runner),'--help'],capture_output=True,text=True)
        self.assertEqual(rejected.returncode,2)
        self.assertIn('Live verification requires assertions',rejected.stderr)


class NegativeFixtureDiagnostics(unittest.TestCase):
    def line(self, index=9):
        return ('ArmorStand[\'Armor Stand\'/3, l=\'ServerLevel[owned]\', x=3.50, y=-188.00, z=3.50]: '
                'Failed to decode value \'{head:{keep_note:"seed-65537-case-'+str(index)+'"},'
                'mainhand:{components:{"minecraft:custom_name":{text:{not_text:['+str(index)+']}}}}}'
                '\' from field \'equipment\': Failed to parse either. First: Not a list: '
                '{text:{not_text:['+str(index)+']}}; Second: No matching codec found missed input: {}')

    def test_expected_rejections_are_scoped_to_the_actual_fixture(self):
        from codec_diagnostics import expected_payload_rejection
        self.assertEqual(expected_payload_rejection(self.line(), 'owned', 65537, 96)['fixture'], 'seed-65537-case-9')
        for line, world, seed, count in [(self.line(), 'other-world', 65537, 96),
                                         (self.line(), 'owned', 1, 96),
                                         (self.line(10), 'owned', 65537, 96),
                                         (self.line(), 'owned', 65537, 9),
                                         (self.line().replace('No matching codec found', 'Unrelated engine error'), 'owned', 65537, 96)]:
            self.assertIsNone(expected_payload_rejection(line, world, seed, count))

    def test_unknown_errors_and_repeated_rejections_still_fail(self):
        from codec_diagnostics import split_payload_diagnostics
        from test_engine import game_lab
        unrelated='Failed to parse function tarot:tick: unknown command'
        filtered, known=split_payload_diagnostics(self.line()+'\n'+unrelated, 'owned', 65537, 96)
        self.assertEqual(len(known), 1)
        with self.assertRaisesRegex(RuntimeError, 'Datapack engine errors'):
            game_lab.VanillaLane.check_log(None, filtered)
        with self.assertRaisesRegex(AssertionError, 'Unexpected codec diagnostic'):
            split_payload_diagnostics(self.line().replace('No matching codec found', 'Unknown failure'), 'owned', 65537, 96)
        with self.assertRaisesRegex(AssertionError, 'exceeded the fixture action count'):
            split_payload_diagnostics('\n'.join([self.line()]*4), 'owned', 65537, 96)


if __name__ == '__main__':
    unittest.main()
