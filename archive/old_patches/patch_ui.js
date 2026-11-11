const fs = require('fs');

const file = 'D:/AGROBOTAI/frontend/src/App.jsx';
let content = fs.readFileSync(file, 'utf8');

const replaceStr = `{activeTab === 'emergency' && (
                    <div>
                      {result.advice?.summary && (
                        <div style={{ background: '#f8fafc', padding: '1rem', borderRadius: '8px', marginBottom: '1rem', borderLeft: '4px solid #059669' }}>
                          <h4 style={{ margin: '0 0 0.5rem 0', color: '#0f172a' }}>{result.advice.summary.headline}</h4>
                          <p style={{ margin: '0 0 0.25rem 0', color: '#334155' }}><strong>Severity:</strong> {result.advice.summary.severity} | <strong>Confidence:</strong> {result.advice.summary.confidence}</p>
                          <p style={{ margin: 0, color: '#475569', fontStyle: 'italic' }}>{result.advice.summary.farmer_message}</p>
                        </div>
                      )}
                      <div className="grid-2">
                      <div>
                      <h4 style={{ color: '#dc2626', marginBottom: '0.5rem', fontWeight: '700' }}>Emergency Actions</h4>
                      {(!result.advice?.emergency_actions || result.advice.emergency_actions.length === 0) ? (
                        <p style={{ color: '#94a3b8', fontStyle: 'italic' }}>No immediate emergency actions required.</p>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                          {result.advice.emergency_actions.map((act, i) => (
                            <div key={i} style={{ padding: '0.75rem', borderRadius: '8px', background: act.priority === 'HIGH' ? '#fee2e2' : '#f1f5f9', borderLeft: act.priority === 'HIGH' ? '4px solid #dc2626' : '4px solid #64748b' }}>
                              <strong style={{ color: act.priority === 'HIGH' ? '#b91c1c' : '#334155' }}>
                                [{act.priority}] {act.action}
                              </strong>
                              {act.reason && <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.9rem', color: '#475569' }}>Because: {act.reason}</p>}
                            </div>
                          ))}
                        </div>
                      )}
                      </div>
                      <div>
                      {result.advice?.safety?.warnings && result.advice.safety.warnings.length > 0 && (
                        <div>
                           <h4 style={{ color: '#b91c1c', marginBottom: '0.5rem', fontWeight: '700' }}>Safety Warnings</h4>
                           {renderAdviceList(result.advice.safety.warnings)}
                        </div>
                      )}
                      </div>
                      </div>
                    </div>
                  )}

                  {activeTab === 'timeline' && (
                    <div className="grid-2">
                      <div>
                        <h4 style={{ color: '#d97706', marginBottom: '0.5rem', fontWeight: '700' }}>Next 24 Hours</h4>
                        {renderAdviceList(result.advice?.schedule?.next_24_hours)}
                      </div>
                      <div>
                        <h4 style={{ color: '#2563eb', marginBottom: '0.5rem', fontWeight: '700' }}>Days 2-7</h4>
                        <div style={{ marginBottom: '1rem' }}>
                          <h5 style={{ margin: '0 0 0.25rem 0', color: '#1d4ed8' }}>Days 2-3</h5>
                          {renderAdviceList(result.advice?.schedule?.days_2_3)}
                        </div>
                        <div>
                          <h5 style={{ margin: '0 0 0.25rem 0', color: '#1d4ed8' }}>Days 4-7</h5>
                          {renderAdviceList(result.advice?.schedule?.days_4_7)}
                        </div>
                      </div>
                    </div>
                  )}

                  {activeTab === 'control' && (
                    <div className="grid-2">
                      <div>
                        <h4 style={{ color: '#059669', marginBottom: '0.5rem', fontWeight: '700' }}>Findings & Verification</h4>
                        <div style={{ marginBottom: '1rem' }}>
                            <h5 style={{ margin: '0 0 0.25rem 0' }}>Confirmed</h5>
                            {renderAdviceList(result.advice?.pest_disease_control?.confirmed_findings)}
                        </div>
                        <div style={{ marginBottom: '1rem' }}>
                            <h5 style={{ margin: '0 0 0.25rem 0' }}>Possible</h5>
                            {renderAdviceList(result.advice?.pest_disease_control?.possible_findings)}
                        </div>
                        <div>
                            <h5 style={{ margin: '0 0 0.25rem 0' }}>Verification Steps</h5>
                            {renderAdviceList(result.advice?.pest_disease_control?.verification_steps)}
                        </div>
                      </div>
                      <div>
                        <h4 style={{ color: '#059669', marginBottom: '0.5rem', fontWeight: '700' }}>Control Methods</h4>
                        <div style={{ marginBottom: '1rem' }}>
                            <h5 style={{ margin: '0 0 0.25rem 0' }}>Cultural</h5>
                            {renderAdviceList(result.advice?.pest_disease_control?.cultural_control)}
                        </div>
                        <div style={{ marginBottom: '1rem' }}>
                            <h5 style={{ margin: '0 0 0.25rem 0' }}>Biological</h5>
                            {renderAdviceList(result.advice?.pest_disease_control?.biological_control)}
                        </div>
                        <div>
                            <h5 style={{ margin: '0 0 0.25rem 0' }}>Chemical</h5>
                            {renderAdviceList(result.advice?.pest_disease_control?.chemical_control)}
                        </div>
                      </div>
                    </div>
                  )}

                  {activeTab === 'nutrition' && (
                    <div className="grid-2">
                      <div>
                        <h4 style={{ color: '#0284c7', marginBottom: '0.5rem', fontWeight: '700' }}>Irrigation & Soil</h4>
                        <div style={{ marginBottom: '1rem' }}>
                            <h5 style={{ margin: '0 0 0.25rem 0' }}>Irrigation Guidance</h5>
                            {renderAdviceList(result.advice?.water_soil_nutrition?.irrigation)}
                        </div>
                        <div>
                            <h5 style={{ margin: '0 0 0.25rem 0' }}>Soil Actions</h5>
                            {renderAdviceList(result.advice?.water_soil_nutrition?.soil_actions)}
                        </div>
                      </div>
                      <div>
                        <h4 style={{ color: '#7c3aed', marginBottom: '0.5rem', fontWeight: '700' }}>Nutrient & Sensor Data</h4>
                        <div style={{ marginBottom: '1rem' }}>
                            <h5 style={{ margin: '0 0 0.25rem 0' }}>Nutrient Management</h5>
                            {renderAdviceList(result.advice?.water_soil_nutrition?.nutrient_actions)}
                        </div>
                        {result.advice?.water_soil_nutrition?.sensor_status && (
                            <div style={{ background: '#f3f4f6', padding: '0.75rem', borderRadius: '8px' }}>
                                <strong>Sensor Status:</strong> {result.advice.water_soil_nutrition.sensor_status}
                            </div>
                        )}
                      </div>
                    </div>
                  )}

                  {activeTab === 'notes' && (
                    <div className="grid-2">
                      <div>
                        <h4 style={{ color: '#475569', marginBottom: '0.5rem', fontWeight: '700' }}>Risk Assessment</h4>
                        <ul className="risk-list" style={{ paddingLeft: '1.2rem', lineHeight: '1.7', color: '#334155' }}>
                            {result.advice?.risk_field_notes?.disease_risk && <li><strong>Disease Risk:</strong> {result.advice.risk_field_notes.disease_risk}</li>}
                            {result.advice?.risk_field_notes?.pest_risk && <li><strong>Pest Risk:</strong> {result.advice.risk_field_notes.pest_risk}</li>}
                            {result.advice?.risk_field_notes?.spread_risk && <li><strong>Spread Risk:</strong> {result.advice.risk_field_notes.spread_risk}</li>}
                            {result.advice?.risk_field_notes?.environmental_risk && <li><strong>Environmental Risk:</strong> {result.advice.risk_field_notes.environmental_risk}</li>}
                        </ul>
                      </div>
                      <div>
                        <h4 style={{ color: '#475569', marginBottom: '0.5rem', fontWeight: '700' }}>Field Monitoring</h4>
                        {renderAdviceList(result.advice?.risk_field_notes?.monitoring_notes)}
                        {result.advice?.risk_field_notes?.next_scan && (
                            <div style={{ marginTop: '1rem', background: '#f8fafc', padding: '0.75rem', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                                <strong>Next Scan Recommended:</strong> {result.advice.risk_field_notes.next_scan}
                            </div>
                        )}
                         {result.advice?.safety?.chemical_disclaimer && (
                            <div style={{ marginTop: '1rem', background: '#fffbeb', padding: '0.75rem', borderRadius: '8px', fontSize: '0.85rem', color: '#b45309' }}>
                                <strong>Disclaimer:</strong> {result.advice.safety.chemical_disclaimer}
                            </div>
                        )}
                      </div>
                    </div>
                  )}
`;

const emergencyIdx = content.indexOf("{activeTab === 'emergency' && (");
const notesIdx = content.indexOf("{activeTab === 'notes' && (");
const endStr = "</div>\n                  )}";
const endNotesIdx = content.indexOf(endStr, notesIdx) + endStr.length;

if (emergencyIdx > -1 && notesIdx > -1 && endNotesIdx > notesIdx) {
    content = content.substring(0, emergencyIdx) + replaceStr + "\n                  {/* Note: UI dynamically injected via patch */}\n" + content.substring(endNotesIdx);
    fs.writeFileSync(file, content, 'utf8');
    console.log("Success via flexible replacement");
} else {
    console.log("Replacement failed.");
}
