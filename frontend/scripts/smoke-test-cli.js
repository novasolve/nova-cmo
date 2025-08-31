#!/usr/bin/env node

/**
 * Headless smoke test CLI for CI/CD integration
 * Usage: node scripts/smoke-test-cli.js [--backend=http://localhost:8000]
 */

const API_URL = process.argv.find(arg => arg.startsWith('--backend='))?.split('=')[1] || 'http://localhost:8000';
const TIMEOUT_MS = 60000; // 60 seconds

async function runSmokeTest() {
  console.log('🧪 Starting headless smoke test...');
  console.log(`📡 Backend: ${API_URL}`);
  
  const startTime = Date.now();
  const threadId = `smoke-cli-${Date.now()}`;
  
  try {
    // Start smoke test
    const response = await fetch(`${API_URL}/api/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        goal: "Find 3 OSS Python maintainers active in the last 30 days",
        dryRun: true,
        config_path: "cmo_agent/config/smoke.yaml",
        metadata: {
          threadId,
          autopilot_level: 0,
          budget_per_day: 1,
          created_by: "smoke_test_cli",
          test_type: "smoke_test"
        }
      })
    });

    if (!response.ok) {
      throw new Error(`Failed to start smoke test: ${response.status} ${await response.text()}`);
    }

    const job = await response.json();
    console.log(`✅ Job created: ${job.id}`);
    
    // Monitor job events
    const eventSource = new (await import('eventsource')).default(`${API_URL}/api/jobs/${job.id}/events`);
    
    const checks = {
      queue_stream: false,
      brief_rendered: false,
      simulation_rendered: false,
      drafts_rendered: false,
      budget_guardrail: false,
      alerts_captured: false,
      summary_rendered: false
    };

    let eventsReceived = 0;
    
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        eventSource.close();
        reject(new Error('Smoke test timed out after 60 seconds'));
      }, TIMEOUT_MS);

      eventSource.onmessage = (event) => {
        eventsReceived++;
        
        try {
          const data = JSON.parse(event.data);
          
          // Update checks based on events
          if (data.event === 'job.progress') {
            checks.queue_stream = true;
            
            if (data.data?.cards_rendered) {
              data.data.cards_rendered.forEach(cardType => {
                if (cardType === 'campaign_brief') checks.brief_rendered = true;
                if (cardType === 'simulation') checks.simulation_rendered = true;
                if (cardType === 'outbox') checks.drafts_rendered = true;
                if (cardType === 'run_summary') checks.summary_rendered = true;
                if (cardType === 'error_group') checks.alerts_captured = true;
              });
            }
          }
          
          if (data.event === 'job.completed' || data.event === 'job.finished') {
            clearTimeout(timeout);
            eventSource.close();
            
            const duration = Date.now() - startTime;
            const passedChecks = Object.values(checks).filter(Boolean).length;
            const totalChecks = Object.keys(checks).length;
            const passed = passedChecks === totalChecks;
            
            console.log(`\n🏁 Smoke test completed in ${(duration/1000).toFixed(1)}s`);
            console.log(`📊 Results: ${passedChecks}/${totalChecks} checks passed`);
            console.log(`📈 Events received: ${eventsReceived}`);
            
            Object.entries(checks).forEach(([check, passed]) => {
              console.log(`  ${passed ? '✅' : '❌'} ${check}`);
            });
            
            if (passed) {
              console.log('\n🎉 Smoke test PASSED');
              resolve(0);
            } else {
              console.log('\n💥 Smoke test FAILED');
              resolve(1);
            }
          }
          
        } catch (error) {
          console.log(`📡 Raw event: ${event.data}`);
        }
      };

      eventSource.onerror = (error) => {
        clearTimeout(timeout);
        eventSource.close();
        reject(new Error(`SSE connection failed: ${error}`));
      };
    });

  } catch (error) {
    console.error('💥 Smoke test failed:', error.message);
    return 1;
  }
}

// Run if called directly
if (require.main === module) {
  runSmokeTest()
    .then(exitCode => process.exit(exitCode))
    .catch(error => {
      console.error('💥 Fatal error:', error.message);
      process.exit(1);
    });
}

module.exports = { runSmokeTest };
