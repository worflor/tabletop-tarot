"""Small algebra and authoring contracts, complementary to actual server tests."""
import itertools
import json
import math
from pathlib import Path
import re
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from optimizations import descending_shuffle
from guidebook import pages, width, WIDTH, HEIGHT, PALETTES, CHAPTERS


class ShuffleAlgebra(unittest.TestCase):
    def test_generated_small_shuffles_have_one_path_per_permutation(self):
        generated=descending_shuffle()
        # Interpret the actual literal ranges and swap indices emitted by the
        # generator; exhaust every random path, rather than sampling RNG output.
        for size in range(2,8):
            steps=[]
            for count in range(size,1,-1):
                source=generated[f'stack/shuffle_step/{count}.mcfunction']
                upper=int(re.search(r'random value 0\.\.(\d+)',source)[1])
                index=int(re.search(r'function tarot:stack/swap_(\d+)',source)[1])
                steps.append((index,range(upper+1)))
            seen=set()
            for choices in itertools.product(*(values for _,values in steps)):
                values=list(range(size))
                for (index,_),other in zip(steps,choices):values[index],values[other]=values[other],values[index]
                seen.add(tuple(values))
            self.assertEqual(len(seen),math.factorial(size))
            self.assertEqual(math.prod(len(values) for _,values in steps),len(seen))

    def test_all_capacity_steps_terminate_and_use_uniform_literal_bounds(self):
        generated=descending_shuffle()
        for size in range(2,129):
            source=generated[f'stack/shuffle_step/{size}.mcfunction']
            self.assertIn(f'random value 0..{size-1}\n',source)
            self.assertIn(f'function tarot:stack/swap_{size-1} with storage tarot:shuffle\n',source)
            self.assertEqual(re.findall(r'function tarot:stack/shuffle_step/(\d+)',source),[str(size-1)] if size>2 else [])


class GuideContract(unittest.TestCase):
    def test_all_ninety_authored_cards_have_readable_linked_pages_in_both_dialects(self):
        for edition in ['steve','alex']:
            with self.subTest(edition=edition):self.check_edition(edition)

    def check_edition(self,edition):
        content=json.loads((ROOT/f'src/guidebook/{edition}.json').read_text())
        entries=[e for section in content['sections'] for e in section['entries']]
        for modern in [False,True]:
            book=pages(content,modern)
            self.assertEqual(len(book),108+bool(content.get('postscript')))
            lookup={p['id']:p for p in book}
            for entry in entries:
                page=lookup[entry['key']]
                self.assertIn(entry['name'].split()[0],page['text'])
                self.assertEqual(' '.join(page['text'].split()).count(' '.join(entry['body'].split())),1)
            for page in book:
                self.assertEqual(len(page['text'].split('\n')),HEIGHT)
                for value in page['component']['extra']:
                    if value['text']!='\n':self.assertLessEqual(width(value['text'],value.get('bold',False)),WIDTH)
                    event=value.get('click_event' if modern else 'clickEvent')
                    if event and event['action']=='change_page':
                        number=event['page' if modern else 'value']
                        self.assertIsInstance(number,int if modern else str)
                        self.assertTrue(1<=int(number)<=len(book))
                    if event:self.assertIn(event['action'],['change_page','copy_to_clipboard'])
                    if event:self.assertTrue(value['underlined'], 'Links must remain identifiable without colour')

    def test_authors_offer_different_readings_and_identical_controls_and_card_identity(self):
        original=json.loads((ROOT/'src/guidebook/content.json').read_text())
        guides=[json.loads((ROOT/f'src/guidebook/{edition}.json').read_text()) for edition in ['steve','alex']]
        def readings(guide):return {e['key']:e for s in guide['sections'] for e in s['entries']}
        expected=readings(original)
        steve,alex=map(readings,guides)
        for content,author in zip(guides,['Steve','Alex']):
            self.assertEqual(content['author'],author)
            self.assertEqual(content['how_to'],original['how_to'])
            self.assertEqual({key:e['name'] for key,e in readings(content).items()},
                             {key:e['name'] for key,e in expected.items()})
        for key in expected:self.assertNotEqual(steve[key]['body'],alex[key]['body'],key)
        # Neither author gets fewer chapters, links, or features.
        def targets(book):
            identities={i+1:p['id'] for i,p in enumerate(book)}
            graph=[]
            for page in book:
                if page['id']=='postscript':continue
                for value in page['component']['extra']:
                    event=value.get('click_event')
                    if not event:continue
                    destination=identities[event['page']] if event['action']=='change_page' else event['value']
                    if destination!='postscript':graph.append((page['id'],value['text'],event['action'],destination))
            return graph
        # Compare actual logical destinations even when the P.S. moves a folio.
        self.assertEqual(targets(pages(guides[0],True)),targets(pages(guides[1],True)))

    def test_small_text_inks_keep_contrast_on_parchment(self):
        def luminance(color):
            values=[int(color[i:i+2],16)/255 for i in [1,3,5]]
            linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
            return sum(a*b for a,b in zip(linear,[.2126,.7152,.0722]))
        # Conservative flat parchment reference; real native screenshots are
        # inspected separately for the textured page and italic overhang.
        paper=luminance('#e4d4aa')
        for ink in [*CHAPTERS.values(),*(v for p in PALETTES.values() for v in p.values())]:
            self.assertGreaterEqual((paper+.05)/(luminance(ink)+.05),4.5,ink)

    def test_an_overlong_body_cannot_silently_clip(self):
        content=json.loads((ROOT/'src/guidebook/content.json').read_text())
        content['sections'][0]['entries'][0]['body']='long page '*90
        with self.assertRaisesRegex(ValueError,'navigation'):pages(content,True)


if __name__=='__main__':unittest.main()
