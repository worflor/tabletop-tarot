"""Streaming must preserve complete canonical receipt bytes and earlier evidence."""
import gzip,hashlib,json,pathlib,tempfile,unittest
from game_lab import write_json,RUNTIME
from receipt_binding import bind_index
from evidence_store import compact

class Receipts(unittest.TestCase):
    def test_log_only_receipt_never_invents_checks_and_legacy_empty_is_bound(self):
        root=RUNTIME/'receipt-tests';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root,prefix='owned-') as temporary:
            path=pathlib.Path(temporary)/'log.json';write_json(path,{'passed':True,'scope':'actual command log'})
            summary=json.loads(path.read_text(encoding='utf-8'));self.assertNotIn('checks',summary);bind_index(path,summary)
            legacy={**summary,'checks':[]};bind_index(path,legacy)
            with self.assertRaisesRegex(ValueError,'lacks binding fields'):
                bind_index(path,{**summary,'checks':[{'name':'invented check','passed':True}]})
    def test_stream_preserves_unicode_nested_payload_and_history(self):
        root=RUNTIME/'receipt-tests';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root,prefix='owned-') as temporary:
            folder=pathlib.Path(temporary).resolve()
            if not folder.is_relative_to(root.resolve()):raise ValueError('Unsafe test root')
            index=folder/'sample.json';data={'passed':True,'commands':[{'name':'café "moon"\n谢谢','cards':[{'x':i,'y':'z'*500} for i in range(200)]}],'protocol_lines':['a\nb'],'checks':[{'name':'whole','passed':True}]}
            expected=(json.dumps(data,indent=2,ensure_ascii=False)+'\n').encode('utf-8')
            for _ in range(2):write_json(index,data)
            summary=json.loads(index.read_text(encoding='utf-8'));ref=summary['full_receipt'];packed=(folder/ref['path']).read_bytes()
            self.assertEqual(gzip.decompress(packed),expected);self.assertEqual(ref['sha256'],hashlib.sha256(packed).hexdigest());self.assertEqual(ref['uncompressed_sha256'],hashlib.sha256(expected).hexdigest())
            historical=json.loads(next((folder/'history').glob('*.json')).read_text(encoding='utf-8'));old=(folder/'history'/historical['full_receipt']['path']).read_bytes()
            self.assertEqual(hashlib.sha256(old).hexdigest(),historical['full_receipt']['sha256']);self.assertEqual(gzip.decompress(old),expected)
            self.assertEqual(bind_index(index,summary),summary)

    def test_summary_cannot_rebind_an_unchanged_archive(self):
        root=RUNTIME/'receipt-tests';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root,prefix='owned-') as temporary:
            index=pathlib.Path(temporary)/'binding.json'
            write_json(index,{'passed':True,'combined_zip_sha256':'old artifact','checks':[{'name':'original check','passed':True}]})
            original=json.loads(index.read_text(encoding='utf-8'))
            for key,value in [('combined_zip_sha256','new artifact'),('passed',False),('checks',[{'name':'invented check','passed':True}])]:
                changed={**original,key:value}
                with self.assertRaisesRegex(ValueError,'differs from archived'):bind_index(index,changed)

    def test_compaction_preserves_history_and_unreferenced_unique_bytes(self):
        root=RUNTIME/'receipt-tests';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root,prefix='owned-') as temporary:
            folder=pathlib.Path(temporary);history=folder/'history';history.mkdir()
            payload=b'{"passed":true,"checks":[]}\n';packed=gzip.compress(payload,mtime=0)
            ref={'path':'old.json.gz','sha256':hashlib.sha256(packed).hexdigest(),'uncompressed_sha256':hashlib.sha256(payload).hexdigest()}
            (folder/'old.json.gz').write_bytes(packed);(history/'old.json.gz').write_bytes(packed)
            for index in [folder/'sample.json',history/'sample.json']:
                index.write_text(json.dumps({'passed':True,'checks':[],'full_receipt':ref}),encoding='utf-8')
            unique=gzip.compress(b'unreferenced earlier diagnostic',mtime=0);(history/'unique.json.gz').write_bytes(unique)
            result=compact(folder)
            self.assertEqual(result['bytes_saved'],len(packed));self.assertEqual(result['indexes_preserved'],2)
            self.assertEqual({p.read_bytes() for p in (folder/'blobs').glob('*.gz')},{packed,unique})
            for index in [folder/'sample.json',history/'sample.json']:bind_index(index,json.loads(index.read_text(encoding='utf-8')))
            self.assertEqual(compact(folder)['retired_copies'],0)

    def test_compaction_refuses_corrupt_reference_before_retiring_anything(self):
        root=RUNTIME/'receipt-tests';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root,prefix='owned-') as temporary:
            folder=pathlib.Path(temporary);archive=folder/'old.json.gz';archive.write_bytes(gzip.compress(b'preserve me'))
            index=folder/'sample.json';index.write_text(json.dumps({'full_receipt':{'path':archive.name,'sha256':'wrong','uncompressed_sha256':'wrong'}}))
            original=index.read_bytes()
            with self.assertRaisesRegex(ValueError,'Compressed receipt mismatch'):compact(folder)
            self.assertTrue(archive.exists());self.assertEqual(index.read_bytes(),original)
if __name__=='__main__':unittest.main()
