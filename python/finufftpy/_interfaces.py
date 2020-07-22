# finufftpy module, ie python-user-facing access to (no-data-copy) interfaces
#
# This is where default opts are stated (in arg list, but not docstring).

# todo: pass opts as python double array, neater?
# Note: this JFM code is an extra level of wrapping beyond DFM's style.
# Barnett 10/31/17: changed all type-2 not to have ms,etc as an input but infer
#                   from size of f.
# Lu 03/10/20: added guru interface calls

# google-style docstrings for napoleon


import finufftpy.finufftpy_cpp as finufftpy_cpp
import numpy as np
import warnings


from finufftpy.finufftpy_cpp import default_opts
from finufftpy.finufftpy_cpp import nufft_opts
from finufftpy.finufftpy_cpp import finufft_plan
from finufftpy.finufftpy_cpp import finufftf_plan


### Plan class definition
class Plan:
    def __init__(self,tp,n_modes_or_dim,iflag=None,n_trans=1,eps=None,**kwargs):
        # set default iflag based on if iflag is None
        if iflag==None:
            if tp==2:
                iflag = -1
            else:
                iflag = 1

        # set opts and check precision type
        opts = nufft_opts()
        default_opts(opts)
        is_single = setkwopts(opts,**kwargs)

        # construct plan based on precision type and eps default value
        if is_single:
            plan = finufftf_plan()
            if eps is None:
                eps = 1e-6
        else:
            plan = finufft_plan()
            if eps is None:
                eps = 1e-14

        # setting n_modes and dim for makeplan
        n_modes = np.ones([3], dtype=np.int64)
        if tp==3:
            npdim = np.asarray(n_modes_or_dim, dtype=np.int)
            if npdim.size != 1:
                raise RuntimeError('FINUFFT type 3 plan n_modes_or_dim must be one number, the dimension')
            dim = int(npdim)
        else:
            npmodes = np.asarray(n_modes_or_dim, dtype=np.int64)
            if npmodes.size>3 or npmodes.size<1:
                raise RuntimeError("FINUFFT n_modes dimension must be 1, 2, or 3")
            dim = int(npmodes.size)
            n_modes[0:dim] = npmodes

        # call makeplan based on precision type
        if is_single:
            ier = finufftpy_cpp.makeplanf(tp,dim,n_modes,iflag,n_trans,eps,plan,opts)
        else:
            ier = finufftpy_cpp.makeplan(tp,dim,n_modes,iflag,n_trans,eps,plan,opts)

        # check error
        if ier != 0:
            err_handler(ier)

        # set C++ side plan as inner_plan
        self.inner_plan = plan

        # set properties
        self.type = tp
        self.dim = dim
        self.n_modes = n_modes
        self.n_trans = n_trans


    ### setpts
    def setpts(self,xj=None,yj=None,zj=None,s=None,t=None,u=None):
        is_single = is_single_plan(self.inner_plan)

        if is_single:
            # array sanity check
            self._xjf = _rchkf(xj)
            self._yjf = _rchkf(yj)
            self._zjf = _rchkf(zj)
            self._sf = _rchkf(s)
            self._tf = _rchkf(t)
            self._uf = _rchkf(u)

            # valid sizes
            dim = self.dim
            tp = self.type
            (self.nj, self.nk) = valid_setpts(tp, dim, self._xjf, self._yjf, self._zjf, self._sf, self._tf, self._uf)

            # call set pts for single prec plan
            ier = finufftpy_cpp.setptsf(self.inner_plan,self.nj,self._xjf,self._yjf,self._zjf,self.nk,self._sf,self._tf,self._uf)
        else:
            # array sanity check
            self._xj = _rchk(xj)
            self._yj = _rchk(yj)
            self._zj = _rchk(zj)
            self._s = _rchk(s)
            self._t = _rchk(t)
            self._u = _rchk(u)

            # valid sizes
            dim = self.dim
            tp = self.type
            (self.nj, self.nk) = valid_setpts(tp, dim, self._xj, self._yj, self._zj, self._s, self._t, self._u)

            # call set pts for double prec plan
            ier = finufftpy_cpp.setpts(self.inner_plan,self.nj,self._xj,self._yj,self._zj,self.nk,self._s,self._t,self._u)

        if ier != 0:
            err_handler(ier)


    ### execute
    def execute(self,data,out=None):
        is_single = is_single_plan(self.inner_plan)

        if is_single:
            _data = _cchkf(data)
            _out = _cchkf(out)
        else:
            _data = _cchk(data)
            _out = _cchk(out)

        tp = self.type
        n_trans = self.n_trans
        nj = self.nj
        nk = self.nk
        dim = self.dim

        if tp==1 or tp==2:
            ms = self.n_modes[0]
            mt = self.n_modes[1]
            mu = self.n_modes[2]

        # input shape and size check
        if tp==2:
            valid_fshape(data.shape,n_trans,dim,ms,mt,mu,None,2)
        else:
            valid_cshape(data.shape,nj,n_trans)

        # out shape and size check
        if out is not None:
            if tp==1:
                valid_fshape(out.shape,n_trans,dim,ms,mt,mu,None,1)
            if tp==2:
                valid_cshape(out.shape,nj,n_trans)
            if tp==3:
                valid_fshape(out.shape,n_trans,dim,None,None,None,nk,3)

        # allocate out if None
        if out is None:
            if is_single:
                pdtype=np.complex64
            else:
                pdtype=np.complex128
            if tp==1:
                _out = np.squeeze(np.zeros([ms, mt, mu, n_trans], dtype=pdtype, order='F'))
            if tp==2:
                _out = np.squeeze(np.zeros([nj, n_trans], dtype=pdtype, order='F'))
            if tp==3:
                _out = np.squeeze(np.zeros([nk, n_trans], dtype=pdtype, order='F'))

        # call execute based on type and precision type
        if tp==1 or tp==3:
            if is_single:
                ier = finufftpy_cpp.executef(self.inner_plan,_data,_out)
            else:
                ier = finufftpy_cpp.execute(self.inner_plan,_data,_out)
        elif tp==2:
            if is_single:
                ier = finufftpy_cpp.executef(self.inner_plan,_out,_data)
            else:
                ier = finufftpy_cpp.execute(self.inner_plan,_out,_data)
        else:
            ier = 10

        # check error
        if ier != 0:
            err_handler(ier)

        # return out
        if out is None:
            return _out
        else:
            _copy(_out,out)
            return out


    def __del__(self):
        destroy(self.inner_plan)
        self.inner_plan = None
### End of Plan class definition



### David Stein's functions for checking input and output variables
def _rchk(x):
    """
    Check if array x is of the appropriate type
    (float64, F-contiguous in memory)
    If not, produce a copy
    """
    if x is not None and x.dtype is not np.dtype('float64'):
        raise RuntimeError('FINUFFT data type must be float64 for double precision float')
    return np.array(x, dtype=np.float64, order='F', copy=False)
def _cchk(x):
    """
    Check if array x is of the appropriate type
    (complex128, F-contiguous in memory)
    If not, produce a copy
    """
    if x is not None and x.dtype is not np.dtype('complex128'):
        raise RuntimeError('FINUFFT data type must be complex128 for double precision complex')
    return np.array(x, dtype=np.complex128, order='F', copy=False)
def _rchkf(x):
    """
    Check if array x is of the appropriate type
    (float64, F-contiguous in memory)
    If not, produce a copy
    """
    if x is not None and x.dtype is not np.dtype('float32'):
        raise RuntimeError('FINUFFT data type must be float32 for single precision float')
    return np.array(x, dtype=np.float32, order='F', copy=False)
def _cchkf(x):
    """
    Check if array x is of the appropriate type
    (complex128, F-contiguous in memory)
    If not, produce a copy
    """
    if x is not None and x.dtype  is not np.dtype('complex64'):
        raise RuntimeError('FINUFFT data type must be complex64 for single precision complex')
    return np.array(x, dtype=np.complex64, order='F', copy=False)
def _copy(_x, x):
    """
    Copy _x to x, only if the underlying data of _x differs from that of x
    """
    if _x.data != x.data:
        x[:] = _x


### error handler
def err_handler(ier):
    switcher = {
        1: 'FINUFFT eps tolerance too small to achieve',
        2: 'FINUFFT malloc size requested greater than MAXNF',
        3: 'FINUFFT spreader fine grid too small compared to kernel width',
        4: 'FINUFFT spreader nonuniform point out of range [-3pi,3pi]^d in type 1 or 2',
        5: 'FINUFFT spreader malloc error',
        6: 'FINUFFT spreader illegal direction (must be 1 or 2)',
        7: 'FINUFFT opts.upsampfac not > 1.0',
        8: 'FINUFFT opts.upsampfac not a value with known Horner polynomial rule',
        9: 'FINUFFT number of transforms ntrans invalid',
        10: 'FINUFFT transform type invalid',
        11: 'FINUFFT general malloc failure',
        12: 'FINUFFT number of dimensions dim invalid'
    }
    err_msg = switcher.get(ier,'Unknown error')

    if ier == 1:
        warnings.warn(err_msg, Warning)
    else:
        raise RuntimeError(err_msg)


### valid sizes when setpts
def valid_setpts(tp,dim,x,y,z,s,t,u):
    if x.ndim != 1:
        raise RuntimeError('FINUFFT x must be a vector')

    nj = x.size

    if tp == 3:
        nk = s.size
        if s.ndim != 1:
            raise RuntimeError('FINUFFT s must be a vector')
    else:
        nk = 0

    if dim > 1:
        if y.ndim != 1:
            raise RuntimeError('FINUFFT y must be a vector')
        if y.size != nj:
            raise RuntimeError('FINUFFT y must have same length as x')
        if tp==3:
            if t.ndim != 1:
                raise RuntimeError('FINUFFT t must be a vector')
            if t.size != nk:
                raise RuntimeError('FINUFFT t must have same length as s')

    if dim > 2:
        if z.ndim != 1:
            raise RuntimeError('FINUFFT z must be a vector')
        if z.size != nj:
            raise RuntimeError('FINUFFT z must have same length as x')
        if tp==3:
            if u.ndim != 1:
                raise RuntimeError('FINUFFT u must be a vector')
            if u.size != nk:
                raise RuntimeError('FINUFFT u must have same length as s')

    return (nj, nk)


### ntransf for type 1 and type 2
def valid_ntr_tp12(dim,shape,n_transin,n_modesin):
    if len(shape) == dim+1:
        n_trans = shape[dim]
        n_modes = shape[0:dim]
    elif len(shape) == dim:
        n_trans = 1
        n_modes = shape
    else:
        raise RuntimeError('FINUFFT type 1 output dimension or type 2 input dimension must be either dim or dim+1(n_trans>1)')

    if n_transin is not None and n_trans != n_transin:
        raise RuntimeError('FINUFFT input n_trans and output n_trans do not match')

    if n_modesin is not None:
        if None not in n_modesin and n_modes != n_modesin:
            raise RuntimeError('FINUFFT input n_modes and output n_modes do not match')

    return (n_trans,n_modes)


### valid number of transforms
def valid_ntr(x,c):
    n_trans = int(c.size/x.size)
    if n_trans*x.size != c.size:
        raise RuntimeError('FINUFFT c.size must be divisible by x.size')
    valid_cshape(c.shape,x.size,n_trans)
    return n_trans


### valid shape of c
def valid_cshape(cshape,xsize,n_trans):
    if n_trans == 1:
        if len(cshape) != 1:
            raise RuntimeError('FINUFFT c.ndim must be 1 if n_trans = 1')
        if cshape[0] != xsize:
            raise RuntimeError('FINUFFT c.size must be same as x.size if n_trans = 1')
    if n_trans > 1:
        if len(cshape) != 2:
            raise RuntimeError('FINUFFT c.ndim must be 2 if n_trans > 1')
        if cshape[0] != xsize or cshape[1] != n_trans:
            raise RuntimeError('FINUFFT c.shape must be (x.size, n_trans) if n_trans > 1')


### valid shape of f
def valid_fshape(fshape,n_trans,dim,ms,mt,mu,nk,tp):
    if tp == 3:
        if n_trans == 1:
            if len(fshape) != 1:
                raise RuntimeError('FINUFFT f.ndim must be 1 for type 3 if n_trans = 1')
            if fshape[0] != nk:
                raise RuntimeError('FINUFFT f.size of must be nk if n_trans = 1')
        if n_trans > 1:
            if len(fshape) != 2:
                raise RuntimeError('FINUFFT f.ndim must be 2 for type 3 if n_trans > 1')
            if fshape[0] != nk or fshape[1] != n_trans:
                raise RuntimeError('FINUFFT f.shape must be (nk, n_trans) if n_trans > 1')
    else:
        if n_trans == 1:
            if len(fshape) != dim:
                raise RuntimeError('FINUFFT f.ndim must be same as the problem dimension for type 1 or 2 if n_trans = 1')
        if n_trans > 1:
            if len(fshape) != dim+1:
                raise RuntimeError('FINUFFT f.ndim must be same as the problem dimension + 1 for type 1 or 2 if n_trans > 1')
            if fshape[dim] != n_trans:
                raise RuntimeError('FINUFFT f.shape[dim] mush be n_trans for type 1 or 2 if n_trans > 1')
        if fshape[0] != ms:
            raise RuntimeError('FINUFFT f.shape[0] mush be ms for type 1 or 2')
        if dim>1:
            if fshape[1] != mt:
                raise RuntimeError('FINUFFT f.shape[1] mush be mt for type 1 or 2')
        if dim>2:
            if fshape[2] != mu:
                raise RuntimeError('FINUFFT f.shape[2] mush be mu for type 1 or 2')


### check if it's a single precision plan
def is_single_plan(plan):
    if type(plan) is finufftpy_cpp.finufftf_plan:
        return True
    elif type(plan) is finufftpy_cpp.finufft_plan:
        return False
    else:
        raise RuntimeError('FINUFFT invalid plan type')


### check if dtype is single or double
def is_single_dtype(dtype):
    if str(dtype).lower() == 'double':
        return False
    elif str(dtype).lower() == 'single':
        return True
    else:
        raise RuntimeError('FINUFFT dtype(precision type) must be single or double')


### kwargs opt set
def setkwopts(opt,**kwargs):
    warnings.simplefilter('always')

    dtype = 'double'
    for key,value in kwargs.items():
        if hasattr(opt,key):
            setattr(opt,key,value)
        elif key == 'dtype':
            dtype = value
        else:
            warnings.warn('Warning: nufft_opts does not have attribute "' + key + '"', Warning)

    warnings.simplefilter('default')

    return is_single_dtype(dtype)


### destroy
def destroy(plan):
    if is_single_plan(plan):
        ier = finufftpy_cpp.destroyf(plan)
    else:
        ier = finufftpy_cpp.destroy(plan)

    if ier != 0:
        err_handler(ier)


### invoke guru interface, this function is used for simple interfaces
def invoke_guru(dim,tp,x,y,z,c,s,t,u,f,isign,eps,n_modes,**kwargs):
    # infer n_modes/n_trans from input/output
    if tp==1:
        n_trans = valid_ntr(x,c)
        if None in n_modes and f is None:
            raise RuntimeError('FINUFFT type 1 input must supply n_modes or output vector, or both')
        if f is not None:
            (n_trans,n_modes) = valid_ntr_tp12(dim,f.shape,n_trans,n_modes)
    elif tp==2:
        (n_trans,n_modes) = valid_ntr_tp12(dim,f.shape,None,None)
    else:
        n_trans = valid_ntr(x,c)

    #plan
    if tp==3:
        plan = Plan(tp,dim,isign,n_trans,eps,**kwargs)
    else:
        plan = Plan(tp,n_modes,isign,n_trans,eps,**kwargs)

    #setpts
    plan.setpts(x,y,z,s,t,u)

    #excute
    if tp==1 or tp==3:
        out = plan.execute(c,f)
    else:
        out = plan.execute(f,c)

    return out

    
### easy interfaces
### 1d1
def nufft1d1(x,c,ms=None,out=None,eps=None,isign=1,**kwargs):
    """1D type-1 (aka adjoint) complex nonuniform fast Fourier transform
  
    ::
  
               nj-1
      f(k1) =  SUM c[j] exp(+/-i k1 x(j))  for -ms/2 <= k1 <= (ms-1)/2
               j=0
  
    Args:
      x     (float[nj]): nonuniform source points, valid only in [-3pi,3pi]
      c     (complex[nj] or complex[nj,ntransf]): source strengths
      isign (int): if >=0, uses + sign in exponential, otherwise - sign
      eps   (float): precision requested (>1e-16)
      ms    (int): number of Fourier modes requested, may be even or odd;
            in either case the modes are integers lying in [-ms/2, (ms-1)/2]
      out   (complex[ms] or complex[ms,ntransf]): output Fourier mode values. Should be initialized as a
            numpy array of the correct size
      **kwargs (nufft_opts + dtype, optional): nufft option fields and precision type as keyword arguments
  
    .. note::
  
      The output is written into the out array if supplied.
  
    Returns:
      ndarray of the result
  
    Example:
      see ``python_tests/demo1d1.py``
    """
    return invoke_guru(1,1,x,None,None,c,None,None,None,out,isign,eps,(ms,),**kwargs)


### 1d2
def nufft1d2(x,f,out=None,eps=None,isign=-1,**kwargs):
    """1D type-2 (aka forward) complex nonuniform fast Fourier transform
  
    ::
  
      c[j] = SUM   f[k1] exp(+/-i k1 x[j])      for j = 0,...,nj-1
              k1
  
  	where sum is over -ms/2 <= k1 <= (ms-1)/2.
  
    Args:
      x     (float[nj]): nonuniform target points, valid only in [-3pi,3pi]
      f     (complex[ms] or complex[ms,ntransf]): Fourier mode coefficients, where ms is even or odd
            In either case the mode indices are integers in [-ms/2, (ms-1)/2]
      isign (int): if >=0, uses + sign in exponential, otherwise - sign
      eps   (float): precision requested (>1e-16)
      out   (complex[nj] or complex[nj,ntransf]): output values at targets. Should be initialized as a
            numpy array of the correct size
      **kwargs (nufft_opts + dtype, optional): nufft option fields and precision type as keyword arguments
  
    .. note::
  
      The output is written into the out array if supplied.
  
    Returns:
      ndarray of the result
  
    Example:
      see ``python_tests/accuracy_speed_tests.py``
    """
    return invoke_guru(1,2,x,None,None,out,None,None,None,f,isign,eps,None,**kwargs)


### 1d3
def nufft1d3(x,c,s,out=None,eps=None,isign=1,**kwargs):
    """1D type-3 (NU-to-NU) complex nonuniform fast Fourier transform
  
    ::
  
  	     nj-1
      f[k]  =  SUM   c[j] exp(+-i s[k] x[j]),      for k = 0, ..., nk-1
  	     j=0
  
    Args:
      x     (float[nj]): nonuniform source points, in R
      c     (complex[nj] or complex[nj,ntransf]): source strengths
      isign (int): if >=0, uses + sign in exponential, otherwise - sign
      eps   (float): precision requested (>1e-16)
      s     (float[nk]): nonuniform target frequency points, in R
      out   (complex[nk] or complex[nk,ntransf]): output values at target frequencies.
            Should be initialized as a numpy array of the correct size
      **kwargs (nufft_opts + dtype, optional): nufft option fields and precision type as keyword arguments
  
    .. note::
  
      The output is written into the out array if supplied.
  
    Returns:
      ndarray of the result
  
    Example:
      see ``python_tests/accuracy_speed_tests.py``
    """
    return invoke_guru(1,3,x,None,None,c,s,None,None,out,isign,eps,None,**kwargs)


### 2d1
def nufft2d1(x,y,c,ms=None,mt=None,out=None,eps=None,isign=1,**kwargs):
    """2D type-1 (aka adjoint) complex nonuniform fast Fourier transform
  
    ::
  
  	            nj-1
  	f(k1,k2) =  SUM c[j] exp(+/-i (k1 x(j) + k2 y[j])),
  	            j=0
  	                  for -ms/2 <= k1 <= (ms-1)/2, -mt/2 <= k2 <= (mt-1)/2
  
    Args:
      x     (float[nj]): nonuniform source x-coords, valid only in [-3pi,3pi]
      y     (float[nj]): nonuniform source y-coords, valid only in [-3pi,3pi]
      c     (complex[nj] or complex[nj,ntransf]): source strengths
      isign (int): if >=0, uses + sign in exponential, otherwise - sign
      eps   (float): precision requested (>1e-16)
      ms    (int): number of Fourier modes in x-direction, may be even or odd;
            in either case the modes are integers lying in [-ms/2, (ms-1)/2]
      mt    (int): number of Fourier modes in y-direction, may be even or odd;
            in either case the modes are integers lying in [-mt/2, (mt-1)/2]
      out   (complex[ms,mt] or complex[ms,mt,ntransf]): output Fourier mode values.
            Should be initialized as a Fortran-ordered (ie ms fast, mt slow) numpy array of the correct size
      **kwargs (nufft_opts + dtype, optional): nufft option fields and precision type as keyword arguments
  
    .. note::
  
      The output is written into the out array if supplied.
  
    Returns:
      ndarray of the result
  
    Example:
      see ``python/tests/accuracy_speed_tests.py``
    """
    return invoke_guru(2,1,x,y,None,c,None,None,None,out,isign,eps,(ms,mt),**kwargs)


### 2d2
def nufft2d2(x,y,f,out=None,eps=None,isign=-1,**kwargs):
    """2D type-2 (aka forward) complex nonuniform fast Fourier transform
  
    ::
  
      c[j] =   SUM   f[k1,k2] exp(+/-i (k1 x[j] + k2 y[j])),  for j = 0,...,nj-1
  	    k1,k2
  
      where sum is over -ms/2 <= k1 <= (ms-1)/2, -mt/2 <= k2 <= (mt-1)/2
  
    Args:
      x     (float[nj]): nonuniform target x-coords, valid only in [-3pi,3pi]
      y     (float[nj]): nonuniform target y-coords, valid only in [-3pi,3pi]
      f     (complex[ms,mt] or complex[ms,mt,ntransf]): Fourier mode coefficients, where ms and mt are
            either even or odd; in either case
  	    their mode range is integers lying in [-m/2, (m-1)/2], with
  	    mode ordering in all dimensions given by modeord.  Ordering is Fortran-style, ie ms fastest.
      isign (int): if >=0, uses + sign in exponential, otherwise - sign
      eps   (float): precision requested (>1e-16)
      out   (complex[nj] or complex[nj,ntransf]): output values at targets. Should be initialized as a
            numpy array of the correct size
      **kwargs (nufft_opts + dtype, optional): nufft option fields and precision type as keyword arguments
  
    .. note::
  
      The output is written into the out array if supplied.
  
    Returns:
      ndarray of the result
  
    Example:
      see ``python_tests/accuracy_speed_tests.py``
    """
    return invoke_guru(2,2,x,y,None,out,None,None,None,f,isign,eps,None,**kwargs)


### 2d3
def nufft2d3(x,y,c,s,t,out=None,eps=None,isign=1,**kwargs):
    """2D type-3 (NU-to-NU) complex nonuniform fast Fourier transform
  
    ::
  
               nj-1
      f[k]  =  SUM   c[j] exp(+-i s[k] x[j] + t[k] y[j]),  for k = 0,...,nk-1
               j=0
  
    Args:
      x     (float[nj]): nonuniform source point x-coords, in R
      y     (float[nj]): nonuniform source point y-coords, in R
      c     (complex[nj] or complex[nj,ntransf]): source strengths
      isign (int): if >=0, uses + sign in exponential, otherwise - sign
      eps   (float): precision requested (>1e-16)
      s     (float[nk]): nonuniform target x-frequencies, in R
      t     (float[nk]): nonuniform target y-frequencies, in R
      out   (complex[nk] or complex[nk,ntransf]): output values at target frequencies.
            Should be initialized as a numpy array of the correct size
      **kwargs (nufft_opts + dtype, optional): nufft option fields and precision type as keyword arguments
  
    .. note::
  
      The output is written into the out array if supplied.
  
    Returns:
      ndarray of the result
  
    Example:
      see ``python_tests/accuracy_speed_tests.py``
  """
    return invoke_guru(2,3,x,y,None,c,s,t,None,out,isign,eps,None,**kwargs)


### 3d1
def nufft3d1(x,y,z,c,ms=None,mt=None,mu=None,out=None,eps=None,isign=1,**kwargs):
    """3D type-1 (aka adjoint) complex nonuniform fast Fourier transform
  
    ::
  
  	           nj-1
      f(k1,k2,k3) =  SUM c[j] exp(+/-i (k1 x(j) + k2 y[j] + k3 z[j])),
  	           j=0
         for -ms/2 <= k1 <= (ms-1)/2,
  	   -mt/2 <= k2 <= (mt-1)/2,  -mu/2 <= k3 <= (mu-1)/2
  
    Args:
      x     (float[nj]): nonuniform source x-coords, valid only in [-3pi,3pi]
      y     (float[nj]): nonuniform source y-coords, valid only in [-3pi,3pi]
      z     (float[nj]): nonuniform source z-coords, valid only in [-3pi,3pi]
      c     (complex[nj] or complex[nj,ntransf]): source strengths
      isign (int): if >=0, uses + sign in exponential, otherwise - sign
      eps   (float): precision requested (>1e-16)
      ms    (int): number of Fourier modes in x-direction, may be even or odd;
            in either case the modes are integers lying in [-ms/2, (ms-1)/2]
      mt    (int): number of Fourier modes in y-direction, may be even or odd;
            in either case the modes are integers lying in [-mt/2, (mt-1)/2]
      mu    (int): number of Fourier modes in z-direction, may be even or odd;
            in either case the modes are integers lying in [-mu/2, (mu-1)/2]
      out   (complex[ms,mt,mu] or complex[ms,mt,mu,ntransf]): output Fourier mode values. 
            Should be initialized as a Fortran-ordered (ie ms fastest) numpy array of the correct size
      **kwargs (nufft_opts + dtype, optional): nufft option fields and precision type as keyword arguments
  
    .. note::
  
      The output is written into the out array if supplied.
  
    Returns:
      ndarray of the result
  
    Example:
      see ``python_tests/accuracy_speed_tests.py``
    """
    return invoke_guru(3,1,x,y,z,c,None,None,None,out,isign,eps,(ms,mt,mu),**kwargs)


### 3d2
def nufft3d2(x,y,z,f,out=None,eps=None,isign=-1,**kwargs):
    """3D type-2 (aka forward) complex nonuniform fast Fourier transform
  
    ::
  
      c[j] =   SUM   f[k1,k2,k3] exp(+/-i (k1 x[j] + k2 y[j] + k3 z[j])).
  	   k1,k2,k3
  	             for j = 0,...,nj-1,  where sum is over
      -ms/2 <= k1 <= (ms-1)/2, -mt/2 <= k2 <= (mt-1)/2, -mu/2 <= k3 <= (mu-1)/2
  
    Args:
      x     (float[nj]): nonuniform target x-coords, valid only in [-3pi,3pi]
      y     (float[nj]): nonuniform target y-coords, valid only in [-3pi,3pi]
      z     (float[nj]): nonuniform target z-coords, valid only in [-3pi,3pi]
      f     (complex[ms,mt,mu] or complex[ms,mt,mu,ntransf]): Fourier mode coefficients, where ms, mt and mu
            are either even or odd; in either case
  	    their mode range is integers lying in [-m/2, (m-1)/2], with
  	    mode ordering in all dimensions given by modeord. Ordering is Fortran-style, ie ms fastest.
      isign (int): if >=0, uses + sign in exponential, otherwise - sign
      eps   (float): precision requested (>1e-16)
      out   (complex[nj] or complex[nj,ntransf]): output values at targets. Should be initialized as a
            numpy array of the correct size
      **kwargs (nufft_opts + dtype, optional): nufft option fields and precision type as keyword arguments
  
    .. note::
  
      The output is written into the out array if supplied.
  
    Returns:
      ndarray of the result
  
    Example:
      see ``python_tests/accuracy_speed_tests.py``
    """
    return invoke_guru(3,2,x,y,z,out,None,None,None,f,isign,eps,None,**kwargs)


### 3d3
def nufft3d3(x,y,z,c,s,t,u,out=None,eps=None,isign=1,**kwargs):
    """3D type-3 (NU-to-NU) complex nonuniform fast Fourier transform
  
    ::
  
               nj-1
      f[k]  =  SUM   c[j] exp(+-i s[k] x[j] + t[k] y[j] + u[k] z[j]),
               j=0
  	                                               for k = 0,...,nk-1
  
    Args:
      x     (float[nj]): nonuniform source point x-coords, in R
      y     (float[nj]): nonuniform source point y-coords, in R
      z     (float[nj]): nonuniform source point z-coords, in R
      c     (complex[nj] or complex[nj,ntransf]): source strengths
      isign (int): if >=0, uses + sign in exponential, otherwise - sign
      eps   (float): precision requested (>1e-16)
      s     (float[nk]): nonuniform target x-frequencies, in R
      t     (float[nk]): nonuniform target y-frequencies, in R
      u     (float[nk]): nonuniform target z-frequencies, in R
      out   (complex[nk] or complex[nk,ntransf]): output values at target frequencies.
            Should be initialized as a numpy array of the correct size
      **kwargs (nufft_opts + dtype, optional): nufft option fields and precision type as keyword arguments
  
    .. note::
  
      The output is written into the out array if supplied.
  
    Returns:
      ndarray of the result
  
    Example:
      see ``python_tests/accuracy_speed_tests.py``
    """
    return invoke_guru(3,3,x,y,z,c,s,t,u,out,isign,eps,None,**kwargs)
