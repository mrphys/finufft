#include "common.h"

BIGINT set_nf(BIGINT ms, nufft_opts opts, spread_opts spopts)
// type 1 & 2 recipe for how to set 1d size of upsampled array given opts
{
  BIGINT nf = 2*(BIGINT)(0.5*opts.R*ms);  // is even
  if (nf<2*spopts.nspread) nf=2*spopts.nspread;  // otherwise spread fails
  // now use next235?
  return nf;
}

void onedim_dct_kernel(BIGINT nf, double *fwkerhalf,
		       double &prefac_unused_dim, spread_opts opts)
/*
  Computes DCT coeffs of cnufftspread's real symmetric kernel, directly,
  exploiting narrowness of kernel.

  Inputs:
  nf - size of 1d uniform spread grid, must be even.
  fwkerhalf - should be allocated for at least nf/2+1 doubles.
  opts - spreading opts object, needed to eval kernel (must be already set up)

  Outputs:
  fwkerhalf - real Fourier coeffs from indices 0 to nf/2 inclusive.
  prefac_unused_dim - the prefactor that cnufftspread multiplies for each
                       unused dimension (ie two such factors in 1d, one in 2d,
		       and none in 3d).
  Single thread only.

  todo: understand how to openmp it? - subtle since private aj's. Want to break
        up fwkerhalf into contiguous pieces, one per thread. Low priority.
  Barnett 1/24/17
 */
{
  int m=opts.nspread/2;                // how many "modes" to include
  double f[HALF_MAX_NS];
  for (int n=0;n<=m;++n)    // actual freq index will be nf/2-n, for cosines
    f[n] = evaluate_kernel((double)n, opts);  // center at nf/2
  prefac_unused_dim = f[0];   // ker @ 0, must match cnufftspread's behavior
  for (int n=1;n<=m;++n)               //  convert from exp to cosine ampls
    f[n] *= 2.0;
  dcomplex a[HALF_MAX_NS],aj[HALF_MAX_NS];
  for (int n=0;n<=m;++n) {             // set up our rotating phase array...
    a[n] = exp(2*M_PI*ima*(double)(nf/2-n)/(double)nf);   // phase differences
    aj[n] = dcomplex{1.0,0.0};         // init phase factors
  }
  for (BIGINT j=0;j<=nf/2;++j) {       // loop along output array
    double x = 0.0;                    // register
    for (int n=0;n<=m;++n) {
      x += f[n] * real(aj[n]);         // only want cosine part
      aj[n] *= a[n];                   // wind the phases
    }
    fwkerhalf[j] = x;
  }
}

void deconvolveshuffle1d(int dir,double prefac,double* ker, BIGINT ms,
			 double *fk, BIGINT nf1, fftw_complex* fw)
/*
  if dir==1: copies fw to fk with amplification by preface/ker
  if dir==2: copies fk to fw (and zero pads rest of it), same amplification.

  fk is complex array stored as 2*ms doubles alternating re,im parts.
  fw is a FFTW style complex array, ie double [nf1][2], essentially doubles
       alternating re,im parts.
  ker is real-valued double array of length nf1/2+1.

  Single thread only.

  It has been tested that the repeated floating division in this inner loop
  only contributes at the <3% level in 3D relative to the fftw cost (8 threads).
  This could be removed by passing in an inverse kernel and doing mults.

  todo: check RAM access in backwards order in 2nd loop is not a speed hit
  todo: check 2*(k0+k)+1 index calcs not slowing us down

  Barnett 1/25/17
*/
{
  BIGINT k0 = ms/2;    // index shift in fk's = magnitude of most neg freq
  if (dir==1) {    // read fw, write out to fk
    for (BIGINT k=0;k<=(ms-1)/2;++k) {               // non-neg freqs k
      fk[2*(k0+k)] = prefac * fw[k][0] / ker[k];          // re
      fk[2*(k0+k)+1] = prefac * fw[k][1] / ker[k];        // im
    }
    for (BIGINT k=-1;k>=-k0;--k) {                 // neg freqs k
      fk[2*(k0+k)] = prefac * fw[nf1+k][0] / ker[-k];     // re
      fk[2*(k0+k)+1] = prefac * fw[nf1+k][1] / ker[-k];   // im
    }
  } else {    // read fk, write out to fw w/ zero padding
    for (BIGINT k=(ms-1)/2;k<nf1-k0;++k)             // zero pad
      fw[k][0] = fw[k][1] = 0.0;
    for (BIGINT k=0;k<=(ms-1)/2;++k) {               // non-neg freqs k
      fw[k][0] = prefac * fk[2*(k0+k)] / ker[k];          // re
      fw[k][1] = prefac * fk[2*(k0+k)+1] / ker[k];        // im
    }
    for (BIGINT k=-1;k>=-k0;--k) {                 // neg freqs k
      fw[nf1+k][0] = prefac * fk[2*(k0+k)] / ker[-k];          // re
      fw[nf1+k][1] = prefac * fk[2*(k0+k)+1] / ker[-k];        // im
    }
  }
}

void deconvolveshuffle2d(int dir,double prefac,double *ker1, double *ker2,
			 BIGINT ms, BIGINT mt,
			 double *fk, BIGINT nf1, BIGINT nf2, fftw_complex* fw)
/*
  2D version of deconvolveshuffle1d, calls it on each x-line using 1/ker2 fac.

  if dir==1: copies fw to fk with amplification by prefac/(ker1(k1)*ker2(k2)).
  if dir==2: copies fk to fw (and zero pads rest of it), same amplification.

  fk is complex array stored as 2*ms*mt doubles alternating re,im parts, with
    ms looped over fast and mt slow.
  fw is a FFTW style complex array, ie double [nf1*nf2][2], essentially doubles
       alternating re,im parts; again nf1 is fast and nf2 slow.
  ker1, ker2 are real-valued double arrays of lengths nf1/2+1, nf2/2+1
       respectively.

  Barnett 2/1/17
*/
{
  BIGINT k02 = mt/2;    // y-index shift in fk's = magnitude of most neg y-freq
  if (dir==2)               // zero pad needed x-lines (contiguous in memory)
    for (BIGINT k=nf1*(mt-1)/2;k<nf1*(nf2-k02);++k)  // k index sweeps all dims
	fw[k][0] = fw[k][1] = 0.0;
  for (BIGINT k2=0;k2<=(mt-1)/2;++k2)               // non-neg y-freqs
    // point fk and fw to the start of this y value's row (2* is for complex):
    deconvolveshuffle1d(dir,prefac/ker2[k2],ker1,ms,fk + 2*ms*(k02+k2),nf1,&fw[nf1*k2]);
  for (BIGINT k2=-1;k2>=-k02;--k2)                 // neg y-freqs
    deconvolveshuffle1d(dir,prefac/ker2[-k2],ker1,ms,fk + 2*ms*(k02+k2),nf1,&fw[nf1*(nf2+k2)]);
}

void deconvolveshuffle3d(int dir,double prefac,double *ker1, double *ker2,
			 double *ker3, BIGINT ms, BIGINT mt, BIGINT mu,
			 double *fk, BIGINT nf1, BIGINT nf2, BIGINT nf3,
			 fftw_complex* fw)
/*
  3D version of deconvolveshuffle2d, calls it on each xy-plane using 1/ker3 fac.

  if dir==1: copies fw to fk with ampl by prefac/(ker1(k1)*ker2(k2)*ker3(k3)).
  if dir==2: copies fk to fw (and zero pads rest of it), same amplification.

  fk is complex array stored as 2*ms*mt*mu doubles alternating re,im parts, with
    ms looped over fastest and mu slowest.
  fw is a FFTW style complex array, ie double [nf1*nf2*nf3][2], effectively
       doubles alternating re,im parts; again nf1 is fastest and nf3 slowest.
  ker1, ker2, ker3 are real-valued double arrays of lengths nf1/2+1, nf2/2+1,
       and nf3/2+1 respectively.

  Barnett 2/1/17
*/
{
  BIGINT k03 = mu/2;    // z-index shift in fk's = magnitude of most neg z-freq
  BIGINT np = nf1*nf2;  // # pts in an upsampled Fourier xy-plane
  if (dir==2)           // zero pad needed xy-planes (contiguous in memory)
    for (BIGINT k=np*(mu-1)/2;k<np*(nf3-k03);++k)  // sweeps all dims
      fw[k][0] = fw[k][1] = 0.0;
  for (BIGINT k3=0;k3<=(mu-1)/2;++k3)               // non-neg z-freqs
    // point fk and fw to the start of this z value's plane (2* is for complex):
    deconvolveshuffle2d(dir,prefac/ker3[k3],ker1,ker2,ms,mt,
			fk + 2*ms*mt*(k03+k3),nf1,nf2,&fw[np*k3]);
  for (BIGINT k3=-1;k3>=-k03;--k3)                 // neg z-freqs
    deconvolveshuffle2d(dir,prefac/ker3[-k3],ker1,ker2,ms,mt,
			fk + 2*ms*mt*(k03+k3),nf1,nf2,&fw[np*(nf3+k3)]);
}