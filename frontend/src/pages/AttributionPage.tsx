import React from 'react'
import './AttributionPage.css'

interface Props {
  onBack: () => void
}

/**
 * Attribution page (REQ-016).
 * Lists all three required dataset attributions with correct licence identifiers.
 */
export default function AttributionPage({ onBack }: Props) {
  return (
    <main className="attribution-page" aria-label="Data attribution">
      <div className="attribution-header">
        <button className="attribution-back" onClick={onBack} aria-label="Back to map">
          ← Back
        </button>
        <h1 className="attribution-title">Data Attribution</h1>
      </div>

      <div className="attribution-body">
        <p className="attribution-intro">
          GeoLens AI is built on the following openly licensed datasets.
          Their terms govern any use of derived outputs.
        </p>

        <section className="attribution-card" aria-labelledby="attr-spacenet">
          <h2 id="attr-spacenet" className="attr-name">SpaceNet Buildings v1 — Rio de Janeiro</h2>
          <dl className="attr-details">
            <dt>Licence</dt>
            <dd>
              <a
                href="https://creativecommons.org/licenses/by-sa/4.0/"
                target="_blank"
                rel="noopener noreferrer"
              >
                CC BY-SA 4.0
              </a>
            </dd>
            <dt>Citation</dt>
            <dd>
              Van Etten et al., "SpaceNet: A Remote Sensing Dataset and Challenge Series",{' '}
              <a
                href="https://arxiv.org/abs/1807.01232"
                target="_blank"
                rel="noopener noreferrer"
              >
                arXiv:1807.01232
              </a>
            </dd>
            <dt>Dataset URL</dt>
            <dd>
              <a
                href="https://spacenet.ai/spacenet-buildings-dataset-v1/"
                target="_blank"
                rel="noopener noreferrer"
              >
                spacenet.ai/spacenet-buildings-dataset-v1
              </a>
            </dd>
          </dl>
          <p className="attr-note">
            The SpaceNet Buildings v1 dataset is used for aerial imagery tiles only.
            Derived model outputs and visualisations are subject to the CC BY-SA 4.0 terms.
          </p>
        </section>

        <section className="attribution-card" aria-labelledby="attr-osm">
          <h2 id="attr-osm" className="attr-name">OpenStreetMap</h2>
          <dl className="attr-details">
            <dt>Licence</dt>
            <dd>
              <a
                href="https://opendatacommons.org/licenses/odbl/"
                target="_blank"
                rel="noopener noreferrer"
              >
                Open Database Licence (ODbL)
              </a>
            </dd>
            <dt>Attribution</dt>
            <dd>© OpenStreetMap contributors</dd>
            <dt>More info</dt>
            <dd>
              <a
                href="https://www.openstreetmap.org/copyright"
                target="_blank"
                rel="noopener noreferrer"
              >
                openstreetmap.org/copyright
              </a>
            </dd>
          </dl>
          <p className="attr-note">
            Map data is © OpenStreetMap contributors, available under the Open Database Licence.
            OSM data used in spatial queries reflects the state at the time of the last
            data_prep.py run (see data/provenance.json for the download date).
          </p>
        </section>

        <section className="attribution-card" aria-labelledby="attr-skyscript">
          <h2 id="attr-skyscript" className="attr-name">SkyScript</h2>
          <dl className="attr-details">
            <dt>Citation</dt>
            <dd>
              Wang et al., "SkyScript: A Large and Semantically Diverse Vision-Language Dataset for Remote Sensing",{' '}
              <a
                href="https://arxiv.org/abs/2312.12856"
                target="_blank"
                rel="noopener noreferrer"
              >
                arXiv:2312.12856
              </a>
            </dd>
          </dl>
          <p className="attr-note">
            SkyCLIP model weights are trained on the SkyScript dataset.
            See the arXiv paper for licence terms applicable to the dataset and model.
          </p>
        </section>

        <section className="attribution-card attribution-card-legal">
          <h2 className="attr-name">Basemap tiles</h2>
          <p className="attr-note">
            Map tiles by{' '}
            <a href="https://carto.com/" target="_blank" rel="noopener noreferrer">CARTO</a>,
            under{' '}
            <a href="https://creativecommons.org/licenses/by/3.0/" target="_blank" rel="noopener noreferrer">
              CC BY 3.0
            </a>.
            Data © OpenStreetMap contributors, ODbL.
          </p>
        </section>
      </div>
    </main>
  )
}
