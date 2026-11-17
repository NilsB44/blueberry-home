// Run with `npm test` (Node strips the types; no test framework needed).
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { current, netWorth, paydays, rebase, type Account } from '../src/lib/economy.ts';

test('counts each 25th after the day the balance was entered', () => {
	assert.equal(paydays('2026-11-17', '2026-11-24'), 0);
	assert.equal(paydays('2026-11-17', '2026-11-25'), 1);
	assert.equal(paydays('2026-11-17', '2026-12-24'), 1);
	assert.equal(paydays('2026-11-17', '2026-12-25'), 2);
});

test('a balance entered on the 25th already holds that saving', () => {
	assert.equal(paydays('2026-11-25', '2026-11-25'), 0);
	assert.equal(paydays('2026-11-25', '2026-12-24'), 0);
	assert.equal(paydays('2026-11-25', '2026-12-25'), 1);
	assert.equal(paydays('2026-11-26', '2026-12-25'), 1);
});

test('crosses years and never goes negative', () => {
	assert.equal(paydays('2026-12-20', '2027-01-25'), 2);
	assert.equal(paydays('2026-11-17', '2027-11-17'), 12);
	assert.equal(paydays('2026-12-01', '2026-11-01'), 0);
});

test('adds the monthly saving to the balance, but not to loans or old accounts', () => {
	const fund: Account = { name: 'Index', kind: 'investment', balance: 1000, monthly: 200, since: '2026-11-17' };
	assert.equal(current(fund, '2027-01-25'), 1600);
	assert.equal(current({ ...fund, since: null }, '2027-01-25'), 1000);
	assert.equal(current({ ...fund, kind: 'loan' }, '2027-01-25'), 1000);
	const loan: Account = { name: 'Mortgage', kind: 'loan', balance: 500 };
	assert.equal(netWorth([fund, loan]), current(fund) - 500);
});

test('rebase keeps the savings so far, so a new amount only counts from today', () => {
	const fund: Account = { name: 'Index', kind: 'investment', balance: 1000, monthly: 200, since: '2026-11-17' };
	rebase(fund, '2026-12-26');
	fund.monthly = 500;
	assert.deepEqual([fund.balance, fund.since], [1400, '2026-12-26']);
	assert.equal(current(fund, '2027-01-25'), 1900);
});
