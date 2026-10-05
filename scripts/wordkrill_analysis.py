#!/usr/bin/env python3
"""
Wordkrill Analysis: Multidimensional text scaling for IHEID theses.

Based on: Riesch, B. (2025). "Wordkrill: Extending Wordfish into the
multidimensional political space." arXiv:2506.20275

This implementation estimates document positions on K latent dimensions
using a Poisson scaling model to identify discriminating vocabulary
between PhD and Master theses.
"""

import os
import re
import json
import numpy as np
import pandas as pd
from collections import Counter
from scipy import sparse
from scipy.optimize import minimize
from scipy.special import gammaln
import warnings
warnings.filterwarnings('ignore')


def load_thesis_texts(alto_dir, consolidated_csv, sample_words=5000):
    """Load thesis texts with metadata."""

    # Load consolidated metadata
    df_meta = pd.read_csv(consolidated_csv)
    doc_to_type = dict(zip(df_meta['doc_id'], df_meta['thesis_type']))

    documents = []
    labels = []
    doc_ids = []

    for filename in os.listdir(alto_dir):
        if not filename.endswith('.txt'):
            continue

        doc_id = filename.replace('.txt', '')
        thesis_type = doc_to_type.get(doc_id)

        if thesis_type not in ['PhD', 'Master/Other']:
            continue

        filepath = os.path.join(alto_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()

            # Extract first N words (avoid bibliographies)
            words = text.split()[:sample_words]
            text = ' '.join(words)

            documents.append(text)
            labels.append(thesis_type)
            doc_ids.append(doc_id)

        except Exception as e:
            continue

    return documents, labels, doc_ids


def preprocess_text(text):
    """Clean and tokenize text."""
    # Lowercase
    text = text.lower()
    # Remove page markers
    text = re.sub(r'---\s*page\s*\d+\s*---', '', text)
    # Keep only letters and spaces
    text = re.sub(r'[^a-zàâäéèêëïîôùûüœæç\s]', ' ', text)
    # Tokenize
    tokens = text.split()
    # Filter short tokens and stopwords
    stopwords = {
        'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'en', 'à', 'au', 'aux',
        'ce', 'cette', 'ces', 'il', 'elle', 'ils', 'elles', 'on', 'nous', 'vous',
        'qui', 'que', 'quoi', 'dont', 'où', 'car', 'mais', 'ou', 'donc', 'ni', 'si',
        'the', 'of', 'and', 'to', 'in', 'is', 'for', 'that', 'with', 'as', 'was',
        'are', 'be', 'this', 'by', 'on', 'at', 'an', 'or', 'from', 'it', 'its',
        'has', 'have', 'had', 'been', 'were', 'will', 'would', 'could', 'should',
        'der', 'die', 'das', 'und', 'ist', 'von', 'mit', 'für', 'auf', 'den', 'dem',
        'pour', 'dans', 'par', 'sur', 'est', 'sont', 'plus', 'peut', 'être', 'fait',
        'also', 'not', 'but', 'more', 'such', 'than', 'their', 'which', 'these',
        'other', 'only', 'some', 'into', 'most', 'they', 'them', 'there', 'been',
        'entre', 'deux', 'ainsi', 'comme', 'bien', 'même', 'tout', 'tous', 'toute',
        'sans', 'sous', 'vers', 'chez', 'après', 'avant', 'depuis', 'selon',
    }
    tokens = [t for t in tokens if len(t) > 2 and t not in stopwords]
    return tokens


def build_dtm(documents, min_df=10, max_df_ratio=0.5):
    """Build document-term matrix."""

    # Tokenize all documents
    tokenized = [preprocess_text(doc) for doc in documents]

    # Count document frequencies
    doc_freq = Counter()
    for tokens in tokenized:
        doc_freq.update(set(tokens))

    # Filter vocabulary
    n_docs = len(documents)
    vocab = [word for word, df in doc_freq.items()
             if df >= min_df and df <= max_df_ratio * n_docs]
    vocab = sorted(vocab)
    word_to_idx = {w: i for i, w in enumerate(vocab)}

    print(f"Vocabulary size: {len(vocab)}")

    # Build sparse DTM
    rows, cols, data = [], [], []
    for i, tokens in enumerate(tokenized):
        word_counts = Counter(tokens)
        for word, count in word_counts.items():
            if word in word_to_idx:
                rows.append(i)
                cols.append(word_to_idx[word])
                data.append(count)

    dtm = sparse.csr_matrix((data, (rows, cols)),
                            shape=(len(documents), len(vocab)))

    return dtm, vocab


class Wordkrill:
    """
    Wordkrill: Multidimensional Poisson scaling model.

    Model: w_ij ~ Poisson(λ_ij)
           log(λ_ij) = α_i + ψ_j + Σ_k β_j^(k) * θ_i^(k)

    Parameters:
        K: number of latent dimensions
        max_iter: maximum iterations
        tol: convergence tolerance
    """

    def __init__(self, K=2, max_iter=100, tol=1e-4):
        self.K = K
        self.max_iter = max_iter
        self.tol = tol

        # Parameters
        self.alpha = None  # Document fixed effects (n_docs,)
        self.psi = None    # Feature fixed effects (n_features,)
        self.beta = None   # Feature weights (n_features, K)
        self.theta = None  # Document positions (n_docs, K)

    def _initialize(self, dtm):
        """Initialize parameters using SVD."""
        n_docs, n_features = dtm.shape

        # Document totals for alpha initialization
        doc_totals = np.array(dtm.sum(axis=1)).flatten()
        self.alpha = np.log(doc_totals / doc_totals.mean() + 1e-10)

        # Feature totals for psi initialization
        feat_totals = np.array(dtm.sum(axis=0)).flatten()
        self.psi = np.log(feat_totals / feat_totals.mean() + 1e-10)

        # SVD of residual log-frequencies for beta/theta initialization
        dtm_dense = dtm.toarray().astype(float)
        dtm_dense[dtm_dense == 0] = 0.5  # Smoothing
        log_freq = np.log(dtm_dense)

        # Remove fixed effects
        residual = log_freq - self.alpha[:, np.newaxis] - self.psi[np.newaxis, :]

        # SVD
        U, S, Vt = np.linalg.svd(residual, full_matrices=False)

        # Initialize theta and beta from first K components
        self.theta = U[:, :self.K] * np.sqrt(S[:self.K])
        self.beta = Vt[:self.K, :].T * np.sqrt(S[:self.K])

        # Normalize theta
        self._normalize_theta()

    def _normalize_theta(self):
        """Normalize theta: mean=0, var=1, cov=0 per dimension."""
        # Center
        self.theta = self.theta - self.theta.mean(axis=0)

        # Orthogonalize and standardize
        Q, R = np.linalg.qr(self.theta)
        self.theta = Q * np.sqrt(self.theta.shape[0])

        # Adjust beta accordingly
        self.beta = self.beta @ R.T / np.sqrt(self.theta.shape[0])

    def _poisson_nll(self, params, X, y, param_type='theta'):
        """Negative log-likelihood for Poisson regression."""
        eta = X @ params
        # Poisson NLL: -Σ(y*eta - exp(eta) - log(y!))
        nll = -np.sum(y * eta - np.exp(eta))
        return nll

    def _poisson_grad(self, params, X, y):
        """Gradient of Poisson NLL."""
        eta = X @ params
        grad = -X.T @ (y - np.exp(eta))
        return grad

    def _estimate_theta_i(self, i, dtm_row, psi, beta):
        """Estimate theta for document i."""
        y = dtm_row
        mask = y > 0
        y_nz = y[mask]

        # Design matrix: [1, beta_j^(1), ..., beta_j^(K)] for each feature
        X = np.column_stack([np.ones(mask.sum()), beta[mask, :]])

        # Initial guess
        x0 = np.concatenate([[self.alpha[i]], self.theta[i, :]])

        # Optimize
        result = minimize(
            self._poisson_nll,
            x0,
            args=(X, y_nz, 'theta'),
            method='L-BFGS-B',
            jac=lambda p, X, y, t: self._poisson_grad(p, X, y),
            options={'maxiter': 50}
        )

        return result.x[0], result.x[1:]  # alpha_i, theta_i

    def _estimate_beta_j(self, j, dtm_col, alpha, theta):
        """Estimate psi and beta for feature j."""
        y = dtm_col
        mask = y > 0
        y_nz = y[mask]

        # Design matrix: [1, theta_i^(1), ..., theta_i^(K)] for each document
        X = np.column_stack([np.ones(mask.sum()), theta[mask, :]])

        # Initial guess
        x0 = np.concatenate([[self.psi[j]], self.beta[j, :]])

        # Optimize
        result = minimize(
            self._poisson_nll,
            x0,
            args=(X, y_nz, 'beta'),
            method='L-BFGS-B',
            jac=lambda p, X, y, t: self._poisson_grad(p, X, y),
            options={'maxiter': 50}
        )

        return result.x[0], result.x[1:]  # psi_j, beta_j

    def fit(self, dtm):
        """Fit Wordkrill model."""
        n_docs, n_features = dtm.shape
        dtm_array = dtm.toarray()

        print(f"Fitting Wordkrill with K={self.K} dimensions...")
        print(f"Documents: {n_docs}, Features: {n_features}")

        # Initialize
        self._initialize(dtm)

        prev_theta = self.theta.copy()

        for iteration in range(self.max_iter):
            # Step 1: Estimate document parameters (alpha, theta)
            for i in range(n_docs):
                self.alpha[i], self.theta[i, :] = self._estimate_theta_i(
                    i, dtm_array[i, :], self.psi, self.beta
                )

            # Step 2: Normalize theta
            self._normalize_theta()

            # Step 3: Estimate feature parameters (psi, beta)
            for j in range(n_features):
                self.psi[j], self.beta[j, :] = self._estimate_beta_j(
                    j, dtm_array[:, j], self.alpha, self.theta
                )

            # Check convergence
            theta_change = np.max(np.abs(self.theta - prev_theta))

            if (iteration + 1) % 10 == 0:
                print(f"  Iteration {iteration + 1}: max theta change = {theta_change:.6f}")

            if theta_change < self.tol:
                print(f"  Converged at iteration {iteration + 1}")
                break

            prev_theta = self.theta.copy()

        return self

    def get_discriminating_words(self, vocab, dimension=0, top_n=30):
        """Get words that discriminate along a dimension."""
        beta_k = self.beta[:, dimension]

        # Sort by beta values
        sorted_idx = np.argsort(beta_k)

        # Top positive (high values on dimension)
        top_positive = [(vocab[i], beta_k[i]) for i in sorted_idx[-top_n:][::-1]]

        # Top negative (low values on dimension)
        top_negative = [(vocab[i], beta_k[i]) for i in sorted_idx[:top_n]]

        return top_positive, top_negative


def analyze_thesis_differences(dtm, labels, vocab, model):
    """Analyze differences between PhD and Master theses."""

    # Get positions
    theta = model.theta

    # Separate by type
    phd_mask = np.array([l == 'PhD' for l in labels])
    master_mask = np.array([l == 'Master/Other' for l in labels])

    results = {
        'phd_positions': theta[phd_mask, :],
        'master_positions': theta[master_mask, :],
        'all_positions': theta,
        'labels': labels,
        'dimensions': {}
    }

    for k in range(model.K):
        phd_mean = theta[phd_mask, k].mean()
        master_mean = theta[master_mask, k].mean()

        top_pos, top_neg = model.get_discriminating_words(vocab, dimension=k)

        results['dimensions'][k] = {
            'phd_mean': phd_mean,
            'master_mean': master_mean,
            'separation': abs(phd_mean - master_mean),
            'top_positive_words': top_pos,
            'top_negative_words': top_neg,
        }

        print(f"\nDimension {k + 1}:")
        print(f"  PhD mean position: {phd_mean:.3f}")
        print(f"  Master mean position: {master_mean:.3f}")
        print(f"  Separation: {abs(phd_mean - master_mean):.3f}")

        if phd_mean > master_mean:
            print(f"  Words associated with PhD (positive beta):")
            for word, beta in top_pos[:10]:
                print(f"    {word}: {beta:.3f}")
            print(f"  Words associated with Master (negative beta):")
            for word, beta in top_neg[:10]:
                print(f"    {word}: {beta:.3f}")
        else:
            print(f"  Words associated with Master (positive beta):")
            for word, beta in top_pos[:10]:
                print(f"    {word}: {beta:.3f}")
            print(f"  Words associated with PhD (negative beta):")
            for word, beta in top_neg[:10]:
                print(f"    {word}: {beta:.3f}")

    return results


def create_visualization(results, output_file):
    """Create interactive visualization of results."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    theta = results['all_positions']
    labels = results['labels']

    # Colors
    colors = ['#1f77b4' if l == 'PhD' else '#ff7f0e' for l in labels]

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            'Document Positions (Dim 1 vs Dim 2)',
            'Distribution on Dimension 1',
            'Top Discriminating Words (Dim 1)',
            'Top Discriminating Words (Dim 2)'
        ),
        specs=[
            [{"type": "scatter"}, {"type": "histogram"}],
            [{"type": "bar"}, {"type": "bar"}]
        ]
    )

    # Scatter plot
    for thesis_type, color in [('PhD', '#1f77b4'), ('Master/Other', '#ff7f0e')]:
        mask = [l == thesis_type for l in labels]
        fig.add_trace(go.Scatter(
            x=theta[mask, 0],
            y=theta[mask, 1] if theta.shape[1] > 1 else np.zeros(sum(mask)),
            mode='markers',
            name=thesis_type,
            marker=dict(color=color, size=5, opacity=0.6)
        ), row=1, col=1)

    # Histogram
    for thesis_type, color in [('PhD', '#1f77b4'), ('Master/Other', '#ff7f0e')]:
        mask = [l == thesis_type for l in labels]
        fig.add_trace(go.Histogram(
            x=theta[mask, 0],
            name=thesis_type,
            marker_color=color,
            opacity=0.7
        ), row=1, col=2)

    # Word bars for dimension 1
    dim1 = results['dimensions'][0]
    words_pos = [w for w, _ in dim1['top_positive_words'][:15]]
    betas_pos = [b for _, b in dim1['top_positive_words'][:15]]
    words_neg = [w for w, _ in dim1['top_negative_words'][:15]]
    betas_neg = [b for _, b in dim1['top_negative_words'][:15]]

    all_words = words_neg[::-1] + words_pos
    all_betas = betas_neg[::-1] + betas_pos
    colors_bar = ['#ff7f0e'] * 15 + ['#1f77b4'] * 15

    fig.add_trace(go.Bar(
        y=all_words,
        x=all_betas,
        orientation='h',
        marker_color=colors_bar,
        showlegend=False
    ), row=2, col=1)

    # Word bars for dimension 2 if exists
    if 1 in results['dimensions']:
        dim2 = results['dimensions'][1]
        words_pos2 = [w for w, _ in dim2['top_positive_words'][:15]]
        betas_pos2 = [b for _, b in dim2['top_positive_words'][:15]]
        words_neg2 = [w for w, _ in dim2['top_negative_words'][:15]]
        betas_neg2 = [b for _, b in dim2['top_negative_words'][:15]]

        all_words2 = words_neg2[::-1] + words_pos2
        all_betas2 = betas_neg2[::-1] + betas_pos2

        fig.add_trace(go.Bar(
            y=all_words2,
            x=all_betas2,
            orientation='h',
            marker_color=['#d62728'] * 15 + ['#2ca02c'] * 15,
            showlegend=False
        ), row=2, col=2)

    fig.update_layout(
        title='Wordkrill Analysis: PhD vs Master Thesis Differences',
        height=900,
        width=1200,
        showlegend=True
    )

    fig.update_xaxes(title_text='Dimension 1', row=1, col=1)
    fig.update_yaxes(title_text='Dimension 2', row=1, col=1)
    fig.update_xaxes(title_text='Position on Dimension 1', row=1, col=2)
    fig.update_xaxes(title_text='Beta coefficient', row=2, col=1)
    fig.update_xaxes(title_text='Beta coefficient', row=2, col=2)

    fig.write_html(output_file)
    print(f"\nVisualization saved to: {output_file}")


def main():
    base_dir = '/Users/jpcointet/Desktop/iheid these'
    alto_dir = os.path.join(base_dir, 'ALTO_text')
    consolidated_csv = os.path.join(base_dir, 'output/consolidated_theses.csv')
    output_dir = os.path.join(base_dir, 'output')

    print("=" * 60)
    print("WORDKRILL ANALYSIS: PhD vs Master Thesis Differences")
    print("=" * 60)

    # Load documents
    print("\n1. Loading thesis documents...")
    documents, labels, doc_ids = load_thesis_texts(
        alto_dir, consolidated_csv, sample_words=5000
    )
    print(f"   Loaded {len(documents)} documents")
    print(f"   PhD: {sum(1 for l in labels if l == 'PhD')}")
    print(f"   Master/Other: {sum(1 for l in labels if l == 'Master/Other')}")

    # Build DTM
    print("\n2. Building document-term matrix...")
    dtm, vocab = build_dtm(documents, min_df=20, max_df_ratio=0.4)
    print(f"   DTM shape: {dtm.shape}")

    # Fit Wordkrill
    print("\n3. Fitting Wordkrill model...")
    model = Wordkrill(K=2, max_iter=50, tol=1e-3)
    model.fit(dtm)

    # Analyze differences
    print("\n4. Analyzing PhD vs Master differences...")
    results = analyze_thesis_differences(dtm, labels, vocab, model)

    # Save results
    print("\n5. Saving results...")

    # Save positions
    positions_df = pd.DataFrame({
        'doc_id': doc_ids,
        'thesis_type': labels,
        'dim1': model.theta[:, 0],
        'dim2': model.theta[:, 1] if model.K > 1 else 0
    })
    positions_df.to_csv(os.path.join(output_dir, 'wordkrill_positions.csv'), index=False)

    # Save discriminating words
    words_data = []
    for k in range(model.K):
        for word, beta in results['dimensions'][k]['top_positive_words']:
            words_data.append({'dimension': k+1, 'word': word, 'beta': beta, 'direction': 'positive'})
        for word, beta in results['dimensions'][k]['top_negative_words']:
            words_data.append({'dimension': k+1, 'word': word, 'beta': beta, 'direction': 'negative'})

    words_df = pd.DataFrame(words_data)
    words_df.to_csv(os.path.join(output_dir, 'wordkrill_words.csv'), index=False)

    # Create visualization
    create_visualization(results, os.path.join(output_dir, 'wordkrill_analysis.html'))

    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)


if __name__ == '__main__':
    main()
