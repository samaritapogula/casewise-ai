import test from 'node:test';
import assert from 'node:assert/strict';
import { createContinuousSpeech } from '../src/continuousSpeech.js';

function fixture() {
  const instances = [];
  const jobs = new Map();
  const statuses = [];
  const errors = [];
  const states = [];
  let transcript = '';
  let interim = '';
  let timestamp = 10000;
  let nextJob = 1;
  class Recognition {
    constructor() { instances.push(this); }
    start() { this.started = true; }
    stop() { this.stopCalled = true; }
    abort() { this.abortCalled = true; }
  }
  const controller = createContinuousSpeech({
    Recognition,
    lang: 'te-IN',
    clock: () => timestamp,
    schedule: fn => { const id = nextJob++; jobs.set(id, fn); return id; },
    cancelSchedule: id => jobs.delete(id),
    onTranscript: text => { transcript = text; },
    onInterim: text => { interim = text; },
    onListening: flag => { states.push(flag); },
    onStatus: text => { statuses.push(text); },
    onError: msg => { errors.push(msg); },
  });
  return {
    controller, instances, jobs, states, statuses, errors,
    transcript: () => transcript,
    interim: () => interim,
    advance: ms => { timestamp += ms; },
    reconnect: () => { const fn = [...jobs.values()][0]; assert.ok(fn); jobs.clear(); fn(); },
  };
}

test('continuous mode reconnects after silence and keeps the earlier transcript', () => {
  const f = fixture();
  f.controller.start();
  assert.equal(f.instances[0].continuous, true);
  assert.equal(f.instances[0].lang, 'te-IN');
  assert.equal(f.instances[0].interimResults, true);
  f.instances[0].onresult({ results: [{ isFinal: true, 0: { transcript: 'నా డిపాజిట్' } }] });
  assert.equal(f.transcript(), 'నా డిపాజిట్');
  f.advance(3500);
  f.instances[0].onend();
  assert.equal(f.jobs.size, 1);
  assert.equal(f.states.at(-1), true);
  f.reconnect();
  assert.equal(f.instances.length, 2);
  f.instances[1].onresult({ results: [{ isFinal: true, 0: { transcript: 'తిరిగి ఇవ్వలేదు' } }] });
  assert.equal(f.transcript(), 'నా డిపాజిట్ తిరిగి ఇవ్వలేదు');
  f.controller.stop();
  assert.equal(f.instances[1].stopCalled, true);
  f.instances[1].onend();
  assert.equal(f.states.at(-1), false);
  assert.equal(f.jobs.size, 0);
});

test('repeated result events never duplicate final speech', () => {
  const f = fixture();
  f.controller.start();
  const evt = { results: [{ isFinal: true, 0: { transcript: 'First sentence' } }, { isFinal: false, 0: { transcript: ' next' } }] };
  f.instances[0].onresult(evt);
  f.instances[0].onresult(evt);
  assert.equal(f.transcript(), 'First sentence');
  assert.equal(f.interim(), 'next');
});

test('manual Stop cancels pending reconnect and prevents unrequested restart', () => {
  const f = fixture();
  f.controller.start();
  f.instances[0].onend();
  assert.equal(f.jobs.size, 1);
  f.controller.stop();
  assert.equal(f.jobs.size, 0);
  assert.equal(f.states.at(-1), false);
});

test('late final result from stop() is retained before end', () => {
  const f = fixture();
  f.controller.start();
  f.controller.stop();
  f.instances[0].onresult({ results: [{ isFinal: true, 0: { transcript: 'final words' } }] });
  f.instances[0].onend();
  assert.equal(f.transcript(), 'final words');
  assert.equal(f.jobs.size, 0);
});

test('blocked speech permission ends safely without reconnect loops', () => {
  const f = fixture();
  f.controller.start();
  f.instances[0].onerror({error: 'service-not-allowed'});
  f.instances[0].onend();
  assert.equal(f.states.at(-1), false);
  assert.equal(f.jobs.size, 0);
  assert.match(f.errors.at(-1), /blocked/);
});

test('too many immediate browser disconnects stop with a meaningful error', () => {
  const f = fixture();
  f.controller.start();
  for (let i=0; i<5; i++) {
    f.instances.at(-1).onend();
    if (f.jobs.size) f.reconnect();
  }
  assert.equal(f.states.at(-1), false);
  assert.match(f.errors.at(-1), /repeatedly ended/);
});

test('cancel aborts audio and prevents callbacks from stale sessions', () => {
  const f = fixture();
  f.controller.start();
  const old = f.instances[0];
  f.controller.cancel();
  assert.equal(old.abortCalled, true);
  old.onresult({results:[{isFinal:true,0:{transcript:'stale'}}]});
  assert.equal(f.transcript(), '');
  assert.equal(f.states.at(-1), false);
});
