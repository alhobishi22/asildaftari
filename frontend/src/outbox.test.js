import {test} from 'node:test';
import assert from 'node:assert/strict';
import {enqueue,acknowledge,uuid} from './outbox.js';
const first={id:'one',op:'v1',collection:'records',method:'POST',body:{amount:20}};
test('UUID generation does not require secure-context randomUUID',()=>{const a=uuid(),b=uuid();assert.match(a,/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);assert.notEqual(a,b)});
test('queues new records, merges offline edits and preserves creation method',()=>{let q=enqueue([],first);q=enqueue(q,{...first,op:'v2',method:'PUT',body:{amount:30}});assert.equal(q.length,1);assert.equal(q[0].method,'POST');assert.equal(q[0].body.amount,30);assert.equal(acknowledge(q,q[0]).length,0)});
test('acknowledgment cannot discard a newer edit queued during upload',()=>{const q=enqueue([first],{...first,op:'v2',body:{amount:50}}),next=acknowledge(q,first);assert.equal(next.length,1);assert.equal(next[0].body.amount,50);assert.equal(next[0].method,'PUT')});
test('failed rows can be repaired and unrelated rows are preserved',()=>{const q=enqueue([{...first,failed:'invalid'},{...first,id:'two',op:'other'}],{...first,op:'retry'});assert.equal(q[0].failed,null);assert.equal(q[1].op,'other')});
test('empty acknowledgments are safe and capacity errors keep original queue',()=>{assert.deepEqual(acknowledge([],first),[]);const full=Array.from({length:300},(_,i)=>({...first,id:String(i)}));assert.throws(()=>enqueue(full,{...first,id:'new'}));assert.equal(full.length,300)});
