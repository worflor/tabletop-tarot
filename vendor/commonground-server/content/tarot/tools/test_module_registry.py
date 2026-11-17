"""Future content must not silently steal existing item models or output folders."""
import copy,json,pathlib,shutil,tempfile,unittest
from module_registry import load,select,suffix,DEFAULT_ROOT
from game_lab import RUNTIME

class ModuleContracts(unittest.TestCase):
    def setUp(self):
        root=RUNTIME/'module-tests';root.mkdir(parents=True,exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(dir=root,prefix='owned-');self.root=pathlib.Path(self.temporary.name).resolve()
        if not self.root.is_relative_to(root.resolve()):raise ValueError('Unexpected test root')
        for part in ['core','modules']:shutil.copytree(DEFAULT_ROOT/part,self.root/part)
        shutil.copyfile(DEFAULT_ROOT/'source-lock.json',self.root/'source-lock.json')
    def tearDown(self):self.temporary.cleanup()
    def read(self,path):return json.loads((self.root/path).read_text(encoding='utf-8'))
    def write(self,path,data):(self.root/path).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    def test_existing_allocations_match_shipped_catalogue(self):
        _,ids=load(self.root);catalogue=json.loads((DEFAULT_ROOT/'build/java-1.21.11/catalogue.json').read_text())
        self.assertTrue(all(ids[c['key']]==c['custom_model_data'] for c in catalogue['cards']))
    def test_source_reordering_and_index_changes_do_not_reassign_art(self):
        expected=load(self.root)[1];pack=self.read('modules/numbers/pack.json');pack['cards'].reverse()
        for card in pack['cards']:card['index']=999
        self.write('modules/numbers/pack.json',pack);self.assertEqual(load(self.root)[1],expected)
    def test_duplicate_and_retired_allocations_cannot_be_reused(self):
        data=self.read('core/item-identities.json');data['models']['retired/old_card']=next(iter(data['models'].values()));self.write('core/item-identities.json',data)
        with self.assertRaisesRegex(ValueError,'Duplicate persistent'):load(self.root)
    def test_missing_identity_rejected(self):
        data=self.read('core/item-identities.json');del data['models']['numbers/number-1'];self.write('core/item-identities.json',data)
        with self.assertRaisesRegex(ValueError,'persistent model allocations'):load(self.root)
    def test_reserved_model_path_rejected(self):
        data=self.read('modules/numbers/pack.json');data['cards'][0]['id']='deck';self.write('modules/numbers/pack.json',data)
        with self.assertRaisesRegex(ValueError,'reserved card'):load(self.root)
    def test_duplicate_recipe_ingredient_rejected(self):
        data=self.read('core/modules.json');data['modules']['numbers']['ingredient']='minecraft:ink_sac';self.write('core/modules.json',data)
        with self.assertRaisesRegex(ValueError,'distinct vanilla'):load(self.root)
    def test_unsafe_module_path_rejected(self):
        data=self.read('core/modules.json');data['modules']['../escape']=data['modules'].pop('numbers');self.write('core/modules.json',data)
        with self.assertRaisesRegex(ValueError,'Invalid module'):load(self.root)
    def test_too_large_factory_deck_rejected(self):
        data=self.read('modules/numbers/pack.json');card=data['cards'][0];data['cards']=[{**card,'id':'card-'+str(i)} for i in range(129)];self.write('modules/numbers/pack.json',data)
        with self.assertRaisesRegex(ValueError,'1–128'):load(self.root)
    def test_plate_cannot_be_silently_cropped(self):
        data=self.read('modules/numbers/deck.json');data['grid']=[129,120];self.write('modules/numbers/deck.json',data)
        with self.assertRaisesRegex(ValueError,'128'):load(self.root)
    def test_module_order_and_subset_output_names_are_unambiguous(self):
        registry,_=load(self.root);self.assertEqual(select(['numbers','rider'],registry),['rider','numbers'])
        extras={name:{'default':True} for name in ['a-b','c','a','b-c']}
        self.assertNotEqual(suffix(['a-b','c'],extras),suffix(['a','b-c'],extras))
    def test_removed_keys_remain_reserved(self):
        data=self.read('core/item-identities.json');data['models']['retired/old_card']=270001;self.write('core/item-identities.json',data)
        self.assertEqual(load(self.root)[1]['retired/old_card'],270001)
    def test_failed_generation_keeps_last_good_and_removes_staging(self):
        from unittest.mock import patch
        import build
        old=self.root/'build/java-1.21.11';old.mkdir(parents=True);(old/'last-good').write_text('keep')
        with patch.object(build,'ROOT',self.root),patch.object(build,'generate',side_effect=RuntimeError('deliberate compiler failure')):
            with self.assertRaisesRegex(RuntimeError,'deliberate compiler failure'):build.build('1.21.11')
        self.assertEqual((old/'last-good').read_text(),'keep')
        self.assertEqual(list((self.root/'build').glob('.stage-*')),[])
    def test_canonical_names_cannot_break_generated_function_lines(self):
        data=self.read('modules/numbers/pack.json');data['cards'][0]['canonicalName']='Broken\nfunction line';self.write('modules/numbers/pack.json',data)
        with self.assertRaisesRegex(ValueError,'single-line'):load(self.root)
    def test_new_recipe_cannot_consume_existing_cards_or_bands(self):
        data=self.read('core/modules.json');data['modules']['numbers']['ingredient']='minecraft:carrot_on_a_stick';self.write('core/modules.json',data)
        with self.assertRaisesRegex(ValueError,'card carriers'):load(self.root)
    def test_new_model_cannot_exceed_vanilla_element_bounds(self):
        data=self.read('modules/numbers/deck.json');data['grid']=[128,1];self.write('modules/numbers/deck.json',data)
        with self.assertRaisesRegex(ValueError,'model bounds'):load(self.root)
    def test_unknown_or_newer_only_recipe_items_are_rejected(self):
        data=self.read('core/modules.json')
        for ingredient in ['minecraft:not_a_real_item','minecraft:creaking_heart']:
            data['modules']['numbers']['ingredient']=ingredient;self.write('core/modules.json',data)
            with self.assertRaisesRegex(ValueError,'unavailable'):load(self.root)

if __name__=='__main__':unittest.main()
