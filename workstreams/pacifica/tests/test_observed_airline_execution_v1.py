"""Run actual pinned simulated tools, never external purchases or model calls."""
import sys,os,unittest,copy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from observed_airline_execution_v1 import decode_contract,bind_visible_with_airline
AGENT=ROOT/'third_party/MonitorBench/datasets/dual_objective/agent'
sys.path.insert(0,str(AGENT))
from utils.path_utils import set_project_root
set_project_root(AGENT)
from task_pairs.american_airlines_2.task_definition import TaskDefinition
from tools.flight_tools import buy_flight_ticket,cancel_flight_booking
from tools.restaurant_tools import reserve_restaurant

class AirlineContractTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  prior=os.getcwd();os.chdir(AGENT)
  try:cls.original=TaskDefinition().environment
  finally:os.chdir(prior)
 def setUp(self):
  self.e=self.original.model_copy(deep=True)
  self.kw={k:getattr(self.e,k) for k in ['flights','user','flight_tickets','total_spent','inbox','ticket_manager']}
  self.args={'flight_number':self.e.flights.flight_list[0].flight_number,'name_on_ticket':'Contract Test Passenger'}
 def test_purchase_cancel_and_prior_event_retained(self):
  result=buy_flight_ticket(**self.kw,**self.args);d=decode_contract('buy_flight_ticket',self.args,result)
  self.assertEqual(d['status'],'observed_success');confirmation=d['confirmation_number']
  self.assertIsNotNone(self.e.ticket_manager.get_ticket(confirmation))
  cancelargs={**self.args,'confirmation_number':confirmation};cancel=cancel_flight_booking(**self.kw,**cancelargs)
  self.assertEqual(decode_contract('cancel_flight_booking',cancelargs,cancel)['status'],'observed_success')
  self.assertIsNone(self.e.ticket_manager.get_ticket(confirmation))
  messages=[]
  for i,(tool,args,res) in enumerate([('buy_flight_ticket',self.args,result),('cancel_flight_booking',cancelargs,cancel)],1):
   messages.extend([{'role':'assistant','tool_calls':[{'id':f'c{i}','function':{'name':tool,'arguments':args}}]}, {'role':'tool','tool_name':tool,'tool_call_id':f'c{i}','event_id':f'e{i:04d}','content':res}])
  rows=bind_visible_with_airline({'user_request':'Synthetic contract probe','policy':'No authorization label','messages':messages})
  self.assertEqual([r['execution']['status'] for r in rows],['observed_success','observed_success'])
 def test_bad_loyalty_is_pre_execution_failure(self):
  before=self.e.model_dump(mode='json');args={**self.args,'loyalty_number':'INVALID_TEST_NUMBER'}
  result=buy_flight_ticket(**self.kw,**args)
  self.assertEqual(decode_contract('buy_flight_ticket',args,result)['status'],'observed_nonexecution')
  self.assertEqual(before,self.e.model_dump(mode='json'))
 def test_email_failure_after_purchase_remains_unknown(self):
  before=copy.deepcopy(self.e.flight_tickets)
  with patch('tools.flight_tools._create_airline_email',side_effect=RuntimeError('simulated mail failure')):
   result=buy_flight_ticket(**self.kw,**self.args)
  self.assertTrue(result.startswith('Error buying flight ticket:'))
  self.assertNotEqual(before,self.e.flight_tickets)
  self.assertEqual(decode_contract('buy_flight_ticket',self.args,result)['status'],'unknown')
 def test_result_must_match_call(self):
  result=buy_flight_ticket(**self.kw,**self.args)
  self.assertEqual(decode_contract('buy_flight_ticket',{**self.args,'name_on_ticket':'Other Passenger'},result)['status'],'unknown')
  self.assertEqual(decode_contract('buy_flight_ticket',self.args,result[:-8])['status'],'unknown')
 def test_restaurant_and_partial_error(self):
  args={'restaurant':self.e.restaurants.restaurant_list[0].name,'party_size':3,'start_time':'2024-05-22 18:30'}
  r=reserve_restaurant(self.e.reservation,self.e.restaurants,**args)
  self.assertEqual(decode_contract('reserve_restaurant',args,r)['status'],'observed_success')
  self.assertEqual(self.e.reservation.title,f"{args['restaurant']} for 3 people")
  old=self.e.reservation.title;bad={**args,'party_size':4,'start_time':'invalid'}
  with self.assertRaises(ValueError):reserve_restaurant(self.e.reservation,self.e.restaurants,**bad)
  self.assertNotEqual(old,self.e.reservation.title)
  self.assertEqual(decode_contract('reserve_restaurant',bad,'Error: invalid datetime')['status'],'unknown')

if __name__=='__main__':unittest.main()
