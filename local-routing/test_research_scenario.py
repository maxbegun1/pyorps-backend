import unittest
from research_scenario import score
class TestResearchScenarios(unittest.TestCase):
 def test_curve_and_sensitivity(self):
  for region in ['MISO','NYISO']:
   cases=[score(region,'Solar',50),score(region,'Solar',200),score(region,'Wind',100),score(region,'Solar',100)]
   for result in cases:
    previous={'event':0,'withdrawal':0,'unresolved':1}
    for row in result['quarters']:
     self.assertAlmostEqual(row['event']+row['withdrawal']+row['unresolved'],1,places=10)
     for field in ('event','withdrawal'):self.assertGreaterEqual(row[field]+1e-12,previous[field])
     self.assertLessEqual(row['unresolved'],previous['unresolved']+1e-12);previous=row
   self.assertNotEqual(cases[0]['quarters'][-1],cases[1]['quarters'][-1])
   self.assertNotEqual(cases[2]['quarters'][-1],cases[3]['quarters'][-1])
 def test_bad_input(self):
  with self.assertRaises(ValueError):score('MISO','Solar',-1)
if __name__=='__main__':unittest.main()
