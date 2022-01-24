# utils to read PM data
import os
import numpy as np
import skimage
from skimage import io
from skimage import transform
from skimage import color
from skimage.util import img_as_ubyte
import math
from math import cos, sin
import matplotlib
import matplotlib.pyplot as plt
import ntpath
import util.util as util
import warnings
import pytorch_ssim
import cv2
import copy

def getPth(dsFd=r'G:\My Drive\ACLab Shared GDrive\datasetPM\danaLab',idx_subj=1, modality='IR', cov='uncover', idx_frm=1):
    if modality in {'depth','IR','PM','RGB'}:   # simple name are image format
        nmFmt = 'image_{:06}.png'       # read in png
    else:
        nmFmt = '{:06d}.npy'        # or read in npy format
    imgPth = os.path.join(dsFd, '{:05d}'.format(idx_subj), modality, cov, nmFmt.format(idx_frm))
    return imgPth

def getImg_dsPM(dsFd=r'G:\My Drive\ACLab Shared GDrive\datasetPM\danaLab',idx_subj=1, modality='IR', cov='uncover', idx_frm=1):
    '''
    directly get image
    :param dsFd:
    :param idx_subj:
    :param modality:
    :param cov:
    :param idx_frm:
    :return:
    '''
    npy_nmSet = {'depthRaw', 'PMarray'}  # mainly use depth raw and PM array
    if modality in npy_nmSet:       # npy format
        nmFmt = '{:06}.npy'
        # imgPth = os.path.join(dsFd, '{:05d}'.format(idx_subj), modality, cov, nmFmt.format(idx_frm))
        # img = np.load(imgPth)
        readFunc = np.load
    else:
        nmFmt = 'image_{:06d}.png'
        readFunc = io.imread
    imgPth = os.path.join(dsFd, '{:05d}'.format(idx_subj), modality, cov, nmFmt.format(idx_frm))
    img = readFunc(imgPth)  # should be 2d array
    img = np.array(img)
    # if len(img.shape)<3:    # all to 3 dim
    #     img = np.expand_dims(img,-1) # add channel to the last
    return img
def affineImg(img, scale=1,deg=0,  shf=(0,0)):
    '''
    scale, rotate and shift around center, same cropped image will be returned with skimage.transform.warp. use anti-clockwise
    :param img:  suppose to be 2D, or HxWxC format
    :param deg:
    :param shf:
    :param scale:
    :return:
    '''
    h,w = img.shape[:2] #
    c_x = (w+1)/2
    c_y = (h+1)/2
    rad = -math.radians(deg) #
    M_2Cs= np.array([
        [scale, 0, -scale * c_x],
        [0, scale, -scale * c_y],
        [0, 0,  1]
    ])
    M_rt = np.array([
        [cos(rad), -sin(rad), 0],
        [sin(rad), cos(rad), 0],
        [0, 0 ,     1]
    ])
    M_2O = np.array([
        [1, 0, c_x+shf[0]],
        [0, 1,  c_y+shf[1]],
        [0, 0 , 1]
                    ])
    # M= M_2O  * M_2Cs
    #M= np.linalg.multi_dot([M_2O, M_rt, M_2Cs]) # [2,2, no shift part?
    M= M_2O @ M_rt @ M_2Cs
    tsfm = transform.AffineTransform(np.linalg.inv(M))
    img_new = transform.warp(img, tsfm, preserve_range=True)
    return img_new

def getPSE(abs_diff, PCS):
    '''
    calculate the percentage of correct estimation
    :param abs_diff:
    :param PSE:
    :return:
    '''
    n_cor = (abs_diff<PCS).sum()
    acc = n_cor/abs_diff.numel()
    return acc

def getDiff(model, dataset, num_test):
    '''
    from the testing set, get all diff and real matrix for accuracy test
    :param model:
    :param opt_test:
    :return:
    '''
    model.eval()
    diff_li = []
    real_li = []
    for i, data in enumerate(dataset):
        if i == num_test:  # only apply our model to opt.num_test images.
            break
        model.set_input(data)  # unpack data from data loader
        model.test()  # run inference
        # real_B = model.real_B.squeeze().cpu().numpy()
        # fake_B = model.fake_B.squeeze().cpu().numpy()

        real_B = model.real_B.cpu().numpy()
        fake_B = model.fake_B.cpu().numpy()
        diff_abs = np.abs(real_B - fake_B)
        diff_li.append(diff_abs)
        real_li.append(real_B)
    # diff_dStk = np.dstack(diff_li)
    # real_dStk = np.dstack(real_li)
    diff_bStk = np.concatenate(diff_li)
    real_bStk = np.concatenate(real_li)
    return diff_bStk, real_bStk

def ts2Img(ts_bch, R=1, nm_cm=None, if_bch=True):
    '''
    take first tensor from tensor bach and save it to image format, io will deal will the differences across domain
    :param ts_bch: direct output from model
    :return: the image format with axis changed ( I think io can save different range directly, so not handle here), suppose to be 3 dim one.
    '''
    if if_bch:
        ts = ts_bch[0]
    else:
        ts = ts_bch
    image_numpy = ts.data.cpu().float().numpy()
    if 1 == R:
        image_numpy = image_numpy.clip(0, 1)
    elif 2 == R:  # suppose to be clip11,  -1 to 1   make this also to 0, 1 version
        # image_numpy = image_numpy.clip(-1, 1)
        image_numpy = ((image_numpy+1)/2).clip(0, 1)
    else:  # otherwise suppose to be uint8 0 ~ 255
        image_numpy = image_numpy.clip(0, 255)
    if image_numpy.shape[0] == 1:  # grayscale to RGB
        if nm_cm:
            cm = plt.get_cmap(nm_cm)
            image_numpy = cm(image_numpy.transpose([1,2,0]))       #  1 x 255 x 4
            # print('after trans', image_numpy.shape)
            image_numpy = image_numpy.squeeze()[..., :3]  # only 3 channels.
            # print('image cut 3 channel', image_numpy.shape)
            image_numpy = image_numpy.transpose([2,0,1])
        else:
            image_numpy = np.tile(image_numpy, (3, 1, 1))   # make to RGB format
    image_numpy = np.transpose(image_numpy, (1, 2, 0))
    return image_numpy  # default float

def getDiff_img(model, dataset, num_test, web_dir, if_saveImg='y', num_imgSv= 500, baseNm ='demo'):
    '''
    loop the function and save the diff and images to web_dir. Rename all the images to demo_{i}_[real\fake]_[A|B].png
    :param model:
    :param opt_test:
    :return: vertically stacked  difference between prediction and real and also the gt.  Result concatenated vertically,which is a very tall array.
    '''
    if_verb = False
    model.eval()
    diff_li = []
    real_li = []
    imgFd = os.path.join(web_dir, 'demoImgs')   # save to demo Images folder
    if if_saveImg=='y':
        if not os.path.exists(imgFd):
            os.mkdir(imgFd)
    pth_realA = os.path.join(imgFd, baseNm + '_real_A_{}.png')
    pth_fakeB = os.path.join(imgFd, baseNm + '_fake_B_{}.png')
    pth_realB = os.path.join(imgFd, baseNm + '_real_B_{}.png')
    for i, data in enumerate(dataset):
        if i == num_test:  # only apply our model to opt.num_test images.
            break
        model.set_input(data)  # unpack data from data loader
        model.test()  # run forward and compute visual
        # img_path = model.get_image_paths()        # save the trouble just use demo
        # short_path = ntpath.basename(img_path[0])
        # name = os.path.splitext(short_path)[0]
        if 0 == i % 100:
            print('{} samples processed'.format(i))

        # currently only work for one channel, multiple channel not set yet.  maybe to 3 channels.
        # real_A_im = model.real_A.squeeze().cpu().numpy()
        # real_B_im = model.real_B.squeeze().cpu().numpy()
        # fake_B_im = model.fake_B.squeeze().cpu().numpy()
        real_A_im = ts2Img(model.real_A)
        real_B_im = ts2Img(model.real_B)
        fake_B_im = ts2Img(model.fake_B)
        if if_verb:
            print('fake_B, min value is {}, max is {}'.format(fake_B_im.min(), fake_B_im.max()))

        if if_saveImg=='y' and i < num_imgSv:    # save controlled number of images from test set
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                io.imsave(pth_realA.format(i), real_A_im)
                io.imsave(pth_fakeB.format(i), fake_B_im)
                io.imsave(pth_realB.format(i), real_B_im)

        real_B = model.real_B.cpu().numpy()
        fake_B = model.fake_B.cpu().numpy()
        diff_abs = np.abs(real_B - fake_B)
        diff_li.append(diff_abs)        # still channel first
        real_li.append(real_B)
    # diff_dStk = np.dstack(diff_li)
    # real_dStk = np.dstack(real_li)
    diff_bStk = np.concatenate(diff_li)
    real_bStk = np.concatenate(real_li)
    return diff_bStk, real_bStk

def test(model, dataset, num_test, web_dir, if_saveImg='y', num_imgSv= 500, baseNm ='demo', R=1, efs_rt = 0.05, pcs_test = 0.05, if_svWhtCmb=False):
    '''
    similar to getDiffImg, direct return all metrics. Current metrics includes mse, mse_efs, psnr, false positive(fp), depends on clip method, R differs,
    pcs_efs only calculates specified one pcs_test and pcs0.1 (fixed)
    pcs_test point threshold will be determined by the R and pcs value together
    diff and real still need to be saved for later PCS curve generation in varied resolutions like nPhy comparison.
    pcs return specific one and also the
    loop the function and save the diff and images to web_dir. Rename all the images to demo_{i}_[real\fake]_[A|B].png
    :param model: the model to generate real image.
    :param opt_test:
    :param R: is the dynamic range, it is based on clipping method. We mainly use the 01 clip so set it to 1.
    :param efs_rt: the effective area ratio, default 0.05
    :param pcs_test: the pcs test point, default 0.05
    :param if_whtScal: if use different body weight to run result again.
    :return: vertically stacked  difference between prediction and real and also the gt.  Result concatenated vertically,which is a very tall array.
    all metrics are returned following diff and real image,in order
     mse, mse_efs, psnr, psnr_efs, pcs_efs, pcs_efs01, ssim, fp
    '''
    if_verb = False
    model.eval()
    diff_li = []
    real_li = []
    fake_li = []
    imgFd = os.path.join(web_dir, 'demoImgs')  # save to demo Images folder
    if if_saveImg=='y':
        if not os.path.exists(imgFd):
            os.makedirs(imgFd)
    pth_realA = os.path.join(imgFd, baseNm + '{}_real_A.png')
    pth_fakeB = os.path.join(imgFd, baseNm + '{}_fake_B{}.png')     # save multi-stage output  id___ n_stg
    pth_realB = os.path.join(imgFd, baseNm + '{}_real_B.png')
    pth_whtCmb = os.path.join(imgFd, baseNm + '{}_wht_cmb.png')
    cnt = 0
    # accumulator
    mse_sum = 0
    mse_efs_sum = 0
    psnr_sum = 0
    psnr_efs_sum = 0
    pcs_efs_sum = 0
    pcs_efs01_sum = 0   # a default pcs0.1
    ssim_sum = 0
    fp_sum = 0          # false positive
    # gen parameters

    if R ==2:
        thr = -1 + R*efs_rt  # the threshold
    else:
        thr = R * efs_rt

    n_stg = model.opt.n_stg

    for i, data in enumerate(dataset):
        # print('get keys', data.keys())
        cnt += 1
        if i == num_test:  # only apply our model to opt.num_test images.
            break
        model.set_input(data)  # unpack data from data loader
        model.test()  # run forward and compute visual, only forward here
        # img_path = model.get_image_paths()        # save the trouble just use demo
        # short_path = ntpath.basename(img_path[0])
        # name = os.path.splitext(short_path)[0]
        if 0 == i % 100:
            print('{} samples processed'.format(i))

        real_A_im = ts2Img(model.real_A, R)        # numpy image 3 channel for saving, clipped
        real_B_im = ts2Img(model.real_B, R)
        # fake_B_im = ts2Img(model.fake_B, R)
        if if_verb:
            print('fake_B, min value is {}, max is {}'.format(fake_B_im.min(), fake_B_im.max()))

        if if_saveImg == 'y' and i < num_imgSv:  # save controlled number of images from test set
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                io.imsave(pth_realA.format(i), img_as_ubyte(real_A_im))
                io.imsave(pth_realB.format(i), img_as_ubyte(real_B_im))
                if hasattr(model, 'fake_Bs'):
                    for j,fake_B in enumerate(model.fake_Bs):
                        fake_B_im = ts2Img(fake_B, R)       # save multiple stage
                        # print('in single fake  max {} min {}'.format(fake_B_im.max(), fake_B_im.min()))
                        io.imsave(pth_fakeB.format(i, j), img_as_ubyte(fake_B_im))
                if hasattr(model, 'fake_B'):      # for
                    fake_B_im = ts2Img(model.fake_B, R)
                    io.imsave(pth_fakeB.format(i,n_stg-1), img_as_ubyte(fake_B_im))

        real_B = model.real_B.cpu().numpy()
        fake_B = model.fake_B.cpu().numpy()     # last stage one
        # print('np real max {} min {}'.format(real_B.max(), real_B.min()))
        # print('np fake max {} min {}'.format(fake_B.max(), fake_B.min()))
        # if run multiple scaling
        if if_svWhtCmb and if_saveImg == 'y' and i < num_imgSv:
            scals = [0.5,  2]       # half and double
            li_fakeB = [real_B_im]      # real as head  real 0~0.85,  fake 0.0022
            fake_B_im  = ts2Img(model.fake_Bs[-1], R)
            # print('real max {} min {}'.format(real_B_im.max(), real_B_im.min()))
            # print('fake  max {} min {}'.format(fake_B_im.max(), fake_B_im.min()))

            li_fakeB.append(fake_B_im)
            for scale in scals:
                dataT = copy.deepcopy(data)
                dataT['phyVec'][:,0] = dataT['phyVec'][:, 0]*scale
                model.set_input(dataT)
                model.test()
                fake_B_im = ts2Img(model.fake_Bs[-1], R)    # very small?
                # print('scale', scale)
                # print('fake shape {} max {} min {}'.format(fake_B_im.shape, fake_B_im.max(), fake_B_im.min()))
                li_fakeB.append(ts2Img(model.fake_B, R))

            img_wtCmb = np.concatenate(li_fakeB, axis=1)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                io.imsave(pth_whtCmb.format(i), img_as_ubyte(img_wtCmb))    # save combined

        # clip fake_B
        if 1 == R:
            fake_B = fake_B.clip(0,1)
        elif 2==R:   # suppose to be clip11,  -1 to 1
            fake_B = fake_B.clip(-1, 1)
        else:       # suppose to be uint8 0 ~ 255
            fake_B = fake_B.clip(0, 255)

        diff_abs = np.abs(real_B - fake_B)
        # metrics
        mseT = (diff_abs**2).mean()
        psnrT = 20*math.log10(R/mseT)   # R depends on clip
        mse_efsT = (diff_abs[real_B>thr]**2).mean() #
        psnr_efsT = 20*math.log10(R/mse_efsT)   # R depends on clip
        n_efs = diff_abs[real_B>thr].size
        pcs_efsT = (diff_abs[real_B>thr]<R*pcs_test).sum()/n_efs
        pcs_efs01T = (diff_abs[real_B>thr]<R*0.1).sum()/n_efs
        ssimT = pytorch_ssim.ssim(model.real_B, model.fake_B).item()    # get value
        fpT = (fake_B[real_B<thr]>thr).sum()/real_B.size
        # accumulation
        mse_sum += mseT
        mse_efs_sum += mse_efsT
        psnr_sum += psnrT
        psnr_efs_sum += psnr_efsT
        pcs_efs_sum += pcs_efsT
        pcs_efs01_sum += pcs_efs01T
        ssim_sum += ssimT
        fp_sum += fpT

        diff_li.append(diff_abs)  # still channel first
        real_li.append(real_B)
        fake_li.append(fake_B)
    # average
    mse = mse_sum / cnt
    mse_efs = mse_efs_sum / cnt
    psnr = psnr_sum / cnt
    psnr_efs = psnr_efs_sum /cnt
    pcs_efs = pcs_efs_sum / cnt
    pcs_efs01 = pcs_efs01_sum /cnt
    ssim = ssim_sum / cnt
    fp = fp_sum / cnt

    # diff_dStk = np.dstack(diff_li)
    # real_dStk = np.dstack(real_li)
    diff_vStk = np.concatenate(diff_li) # default 1st dim so vertically
    real_vStk = np.concatenate(real_li)
    fake_vStk = np.concatenate(fake_li)
    return fake_vStk, real_vStk, mse, mse_efs, psnr, psnr_efs, pcs_efs, pcs_efs01, ssim, fp

def genPCS(diff_vStk, real_vStk, x, thresh=0.05):
    '''
    generate the PCS vec against x according to preds diff and real values. Only calculate the interesting sensing according to thresh.
    :param diff_vStk:
    :param real_vStk:
    :param x:
    :param thresh: the threshold for interesting sensing.
    :return:
    '''
    y_li = []
    for i in range(len(x)):
        acc = (diff_vStk[real_vStk > thresh] < x[i]).sum() / diff_vStk[real_vStk > thresh].size
        y_li.append(acc)
    return np.array(y_li)   # into array

def drawPCS(rst_li, legend_li, pltNm, rstRt='./results', rgSt= 0, rgTo=0.1, step=11, thresh=0.05,fmt = 'pdf', idx_bold = -1, titleNm = '', sz_lgd = 18, ver=2):
    '''
    plot the PCS in one plot with given rst name list and legends. PCS plot will be saved to <rstRt>/PCSplots with given <pltNm>.
    :param rst_li: is the result folder list when created.
    :param legend_li:
    :param pltNm:
    :param rstRt:
    :param rgTo:
    :param step:
    :param thresh: control the interesting pressure points
    :param sz_lgd: the size of legend
    :param ver: the version number, in version 1, the diff format is different than version 2. We will mainly use version 2 in future. version 1 is only kept for compatibility in case we need plot from old result
    :return:
    '''
    plt.rc('font', family='Times New Roman')
    # plt.rcParams["font.family"] = "Times New Roman"
    # matplotlib.rc('xtick', labelsize=15)
    # matplotlib.rc('ytick', labelsize=15)
    # matplotlib.rc('axes', labelsize=18, titlesize=15)
    # matplotlib.rc('legend', fontsize=18)

    matplotlib.rc('xtick', labelsize=sz_lgd)        # 22 originally
    matplotlib.rc('ytick', labelsize=sz_lgd)
    matplotlib.rc('axes', labelsize=sz_lgd, titlesize=sz_lgd)
    matplotlib.rc('legend', fontsize=sz_lgd)
    # matplotlib.rc('title', fontsize=18)
    # font = {'family': 'Times New Roman',
    #         'weight': 'normal',
    #         'size': 10}
    # matplotlib.rc('font', family='Times New Roman')
    # matplotlib.rc('font', **font)
    # plt.rcParams["font.family"] = 'Times New Roman'
    # matplotlib.rc('text', usetex = True)

    if not len(rst_li) == len(legend_li):
        print('rst list and legend list can not match')
        return -1

    x = np.linspace(rgSt, rgTo, step)
    # y_li = []
    # for pcs in range(len(x)):

    for i, rstFd in enumerate(rst_li):
        if 'clip11' in rstFd:
            bs_sensing = -1
            rg_sensing = 2
            x_calc = rg_sensing * x
        elif 'clip01' in rstFd:
            bs_sensing = 0
            rg_sensing = 1
            x_calc = rg_sensing * x
        else:
            print('no such pmDsProc, exit1')
            os.exit(-1)
        PM_thresh = bs_sensing + rg_sensing * thresh

        if 2 != ver:
            diffPth = os.path.join(rstRt, rstFd, 'test_latest', 'test_diff.npz')
            dataLd = np.load(diffPth)
            diff_vStk = dataLd['diff_dStk']
            real_vStk = dataLd['real_dStk']
        else:
            diffPth = os.path.join(rstRt, rstFd, 'test_latest', 'test_diffV2.npz')
            dataLd = np.load(diffPth)
            fake_vStk = dataLd['fake_vStk']
            real_vStk = dataLd['real_vStk']
            diff_vStk = np.abs(real_vStk - fake_vStk)

        # gen y_rst  from x list
        y = genPCS(diff_vStk, real_vStk, x_calc, thresh=PM_thresh) *100
        if i == idx_bold:
            plt.plot(x,y, label=legend_li[i], linewidth=3)
        else:
            plt.plot(x, y, label=legend_li[i])
    legd = plt.legend(loc='upper left')
    plt.xlabel('Normalized Threshold')
    plt.ylabel('PCS (%)')
    if titleNm:
        plt.title(titleNm)
    plt.gcf().subplots_adjust(bottom=0.2)  # make some rooms
    plt.gcf().subplots_adjust(left=0.2)  # make some rooms
    # emphasize
    for i, text in enumerate(legd.get_texts()):    # can't set individual font
        # print('text', i)
        if idx_bold == i:
            # print('set', i)
            font = {'family':'Times New Roman',
                    'weight':'bold',
                     'size':sz_lgd
                    }
            fontProp = matplotlib.font_manager.FontProperties(**font)
            # text.set_fontweight('bold')
            text.set_fontproperties(fontProp)
    # save the result
    PCSfd = os.path.join(rstRt, 'PCSplots')
    if not os.path.exists(PCSfd):
        os.mkdir(PCSfd)
    pth_save = os.path.join(rstRt, 'PCSplots', pltNm + '.' + fmt)   # default pdf
    plt.savefig(pth_save)   # there is white margin
    # plt.show()

def drawPCSv2(rst_li, legend_li, pltNm, rstRt='./results', rgSt= 0, rgTo=0.1, step=11, thresh=0.05,fmt = 'pdf', idx_bold = -1, titleNm = '', sz_lgd = 18):
    '''
    plot the PCS in one plot with given rst name list and legends. PCS plot will be saved to <rstRt>/PCSplots with given <pltNm>.
    :param rst_li: is the result folder list when created.
    :param legend_li:
    :param pltNm:
    :param rstRt:
    :param rgTo:
    :param step:
    :param thresh: control the interesting pressure points
    :param sz_lgd: the size of legend
    :return:
    '''
    plt.rc('font', family='Times New Roman')
    # plt.rcParams["font.family"] = "Times New Roman"
    # matplotlib.rc('xtick', labelsize=15)
    # matplotlib.rc('ytick', labelsize=15)
    # matplotlib.rc('axes', labelsize=18, titlesize=15)
    # matplotlib.rc('legend', fontsize=18)

    matplotlib.rc('xtick', labelsize=sz_lgd)        # 22 originally
    matplotlib.rc('ytick', labelsize=sz_lgd)
    matplotlib.rc('axes', labelsize=sz_lgd, titlesize=sz_lgd)
    matplotlib.rc('legend', fontsize=sz_lgd)
    # matplotlib.rc('title', fontsize=18)
    # font = {'family': 'Times New Roman',
    #         'weight': 'normal',
    #         'size': 10}
    # matplotlib.rc('font', family='Times New Roman')
    # matplotlib.rc('font', **font)
    # plt.rcParams["font.family"] = 'Times New Roman'
    # matplotlib.rc('text', usetex = True)

    if not len(rst_li) == len(legend_li):
        print('rst list and legend list can not match')
        return -1

    x = np.linspace(rgSt, rgTo, step)
    # y_li = []
    # for pcs in range(len(x)):

    for i, rstFd in enumerate(rst_li):
        # if 'clip11' in rstFd:
        #     bs_sensing = -1
        #     rg_sensing = 2
        #     x_calc = rg_sensing * x
        # elif 'clip01' in rstFd:
        #     bs_sensing = 0
        #     rg_sensing = 1
        #     x_calc = rg_sensing * x
        # else:
        #     print('no such pmDsProc, exit1')
        #     os.exit(-1)
        if 'pix2pix' in rstFd or 'cycle_gan' in rstFd:
            bs_sensing = - 1
            rg_sensing = 2
            x_calc = rg_sensing * x
        else:
            bs_sensing = 0
            rg_sensing = 1
            x_calc = rg_sensing * x

        PM_thresh = bs_sensing + rg_sensing * thresh

        diffPth = os.path.join(rstRt, rstFd, 'test_latest', 'test_diffV2.npz')
        dataLd = np.load(diffPth)
        fake_vStk = dataLd['fake_vStk']
        real_vStk = dataLd['real_vStk']
        diff_vStk = np.abs(real_vStk - fake_vStk)

        # gen y_rst  from x list
        y = genPCS(diff_vStk, real_vStk, x_calc, thresh=PM_thresh) *100
        if i == idx_bold:
            plt.plot(x,y, label=legend_li[i], linewidth=3)
        else:
            plt.plot(x, y, label=legend_li[i])
    legd = plt.legend(loc='upper left')
    plt.xlabel('Normalized Threshold')
    plt.ylabel('PCS (%)')
    if titleNm:
        plt.title(titleNm)
    plt.gcf().subplots_adjust(bottom=0.2)  # make some rooms
    plt.gcf().subplots_adjust(left=0.2)  # make some rooms
    plt.grid(True)
    # emphasize
    for i, text in enumerate(legd.get_texts()):    # can't set individual font
        # print('text', i)
        if idx_bold == i:
            # print('set', i)
            font = {'family':'Times New Roman',
                    'weight':'bold',
                     'size':sz_lgd
                    }
            fontProp = matplotlib.font_manager.FontProperties(**font)
            # text.set_fontweight('bold')
            text.set_fontproperties(fontProp)
    # save the result
    PCSfd = os.path.join(rstRt, 'PCSplots')
    if not os.path.exists(PCSfd):
        os.mkdir(PCSfd)
    pth_save = os.path.join(rstRt, 'PCSplots', pltNm + '.' + fmt)   # default pdf
    print('saving to {}'.format(pth_save))
    plt.savefig(pth_save)   # there is white margin
    # plt.show()
    plt.clf()

def drawGrid(nmLs, idxLs, mod=0, rstFd = 'results', name='base', if_gray = True, if_show = False, subNm = '', dpi = 300):
    '''
    draw the grid pictures from given model with fake colors.  nModel x n_images.  Different mod to draw different combination.
    This version is for single stage, version where demos are named as [real/fake]_[A|B}_[idx].png
    :param nmLs:
    :param idxLs:
    :param mod: default 0 draw only the model output.  1 draw input only, 2 for output only
    :param rstFd:   result folder
    :return:
    '''
    gridFd = os.path.join(rstFd, 'demoGrids', subNm)
    if not os.path.exists(gridFd):
        os.mkdir(gridFd)
    pth = os.path.join(rstFd, '{}', 'test_latest', 'demoImgs', 'demo_{}_{}.png')  # model, fake_B, idx
    # nr = len(nmLs)
    # nc = len(idxLs)
    imgLs = []

    for i, nm in enumerate(nmLs):
        for j in idxLs:
            if 0 == mod:
                img = io.imread(pth.format(nm, 'fake_B', j))
            elif 1 == mod:
                img = io.imread(pth.format(nm, 'real_A', j))
            elif 2 == mod:
                img = io.imread(pth.format(nm, 'real_B', j))
            # plot version ###
            # plt.subplot(nr, nc, i*nc+j+1)
            # plt.imshow(img, cmap = plt.cm.jet)
            # plt.xticks([])
            # plt.yticks([])
            if if_gray:
                if len(img.shape)>2:
                    img = color.rgb2gray(img)
            elif len(img.shape)<3:
                img = color.gray2rgb(img)
            imgLs.append(skimage.img_as_float(img))

    arr_con = np.array(imgLs)
    img_grid = gallery(arr_con, ncols=len(idxLs))
    plt.imshow(img_grid,  cmap=plt.cm.jet)
    plt.xticks([])
    plt.yticks([])
    # get rid of margin
    plt.gca().set_axis_off()
    plt.subplots_adjust(top=1, bottom=0, right=1, left=0,
                    hspace=0, wspace=0)
    plt.margins(0, 0)
    plt.gca().xaxis.set_major_locator(plt.NullLocator())
    plt.gca().yaxis.set_major_locator(plt.NullLocator())
    # print('dpi is', dpi)
    plt.savefig(os.path.join(gridFd, name+'.png'), bbox_inches='tight',
            pad_inches=0, dpi=dpi)      # set dpi
    # plt.savefig(os.path.join(gridFd, name+'.png'))  # same images
    if if_show:
        plt.show()


def drawGridV2(nmLs, idxLs, nmSht_li = [], mod=0, rstFd='results', name='base', subNm='', n_stg=2, if_gray=True, if_show=False, dpi=300):
    '''
    draw the grid pictures from given model with fake colors.  nModel x n_images.  Different mod to draw different combination.
    This version is for multi stage version to draw different stage images.
    :param nmLs:
    :param idxLs:
    :param nmSht_li: the short name for all results,
    :param mod: default 0 draw only the model output.  1 draw input only, 2 ground truth
    :param rstFd:   result folder
    :param name: how to name generated picture
    :param subNm: save all images to specific subFd. So we can indicate which images are for.
    :param n_stg：the stage number for showing the result. start from 0
    :param if_show: if show the image after generation
    :param dpi: the resolution of output image
    :return:
    '''
    gridFd = os.path.join(rstFd, 'demoGrids', subNm)
    if not os.path.exists(gridFd):
        os.mkdir(gridFd)
    pth = os.path.join(rstFd, '{}', 'test_latest', 'demoImgs', 'demo{}_{}{}.png')  # model, fake_B, idx
    # nr = len(nmLs)
    # nc = len(idxLs)
    imgLs = []

    for i, nm in enumerate(nmLs):       # loop the result folder
        for j in idxLs:
            if 0 == mod:
                img = io.imread(pth.format(nm, j, 'fake_B', n_stg))
            elif 1 == mod:
                img = io.imread(pth.format(nm, j, 'real_A', ''))
            elif 2 == mod:
                img = io.imread(pth.format(nm, j, 'real_B', ''))    # empty for stage for real one
            if if_gray: # use pseudo color
                if len(img.shape)>2:
                    img = color.rgb2gray(img)
                    # img = skimage.img_as_ubyte(img)
                    # img = cv2.applyColorMap(img, cv2.COLORMAP_JET)
                    # img = img[:, :, ::-1]    # BGR(cv) to RGB
            elif len(img.shape)<3:
                img = color.gray2rgb(img)
            img = skimage.img_as_ubyte(img) # put all to color format for demo
            if j == 0 and nmSht_li:  # if name provided
                cv2.putText(img, nmSht_li[i], (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            imgLs.append(skimage.img_as_float(img))

    arr_con = np.array(imgLs)
    img_grid = gallery(arr_con, ncols=len(idxLs))
    plt.imshow(img_grid,  cmap=plt.cm.jet)
    plt.xticks([])
    plt.yticks([])
    # get rid of margin
    plt.gca().set_axis_off()
    plt.subplots_adjust(top=1, bottom=0, right=1, left=0,
                    hspace=0, wspace=0)
    plt.margins(0, 0)
    plt.gca().xaxis.set_major_locator(plt.NullLocator())
    plt.gca().yaxis.set_major_locator(plt.NullLocator())
    # print('dpi is', dpi)
    plt.savefig(os.path.join(gridFd, name+'.png'), bbox_inches='tight',
            pad_inches=0, dpi=dpi)      # set dpi
    # plt.savefig(os.path.join(gridFd, name+'.png'))  # same images
    if if_show:
        plt.show()

def drawGridV3(nmLs, idxLs, nmSht_li = [], mod=0, rstFd='results', name='base', subNm='', n_stg=2, if_gray=True, if_show=False, dpi=300, scale=1, clrBg='', thr_bg =0.05, fontScale=1.2):
    '''
    This version directly employ the cv2 engine for pseudo color and text embedding. Save the trouble of plot.
    :param nmLs:
    :param idxLs:
    :param nmSht_li: the short name for all results,
    :param mod: default 0 draw only the model output.  1 draw input only, 2 ground truth
    :param rstFd:   result folder
    :param name: how to name generated picture
    :param subNm: save all images to specific subFd. So we can indicate which images are for.
    :param n_stg：the stage number for showing the result. start from 0
    :param if_show: if show the image after generation
    :param dpi: the resolution of output image
    :param if_gray: if use gray pseudo color
    :param scale: the scale factor for higher contrast by reducing the dynamic range.  Our of range area will be saturated.
    :param clrBg: color bg, blank for original blue bg.
    :return:
    '''
    gridFd = os.path.join(rstFd, 'demoGrids', subNm)
    if not os.path.exists(gridFd):
        os.makedirs(gridFd)
    pth = os.path.join(rstFd, '{}', 'test_latest', 'demoImgs', 'demo{}_{}{}.png')  # model, fake_B, idx
    # nr = len(nmLs)
    # nc = len(idxLs)
    imgLs = []

    for i, nm in enumerate(nmLs):       # loop the result folder
        print('processing', nm)
        for cnt, j in enumerate(idxLs):
            if 0 == mod:
                img = cv2.imread(pth.format(nm, j, 'fake_B', n_stg))
            elif 1 == mod:
                img = cv2.imread(pth.format(nm, j, 'real_A', ''))
            elif 2 == mod:
                img = cv2.imread(pth.format(nm, j, 'real_B', ''))    # empty for stage for real one
            img = (img* scale).astype('uint8').clip(0, 255)     # cv2 will employ 255 range
            imgM = img.copy()
            if if_gray: # if use gray pseudo color
                if len(img.shape)>2:
                    # img = color.rgb2gray(img)   # if single to color
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                # img = skimage.img_as_ubyte(img)
                img = cv2.applyColorMap(img, cv2.COLORMAP_JET)      # transfer on individual image only. shouldn't be a problem
                if clrBg == 'black':
                    img[imgM < thr_bg * 255] = 0
                elif clrBg == 'white':
                    img[imgM < thr_bg * 255] = 255


            if cnt == 0 and nmSht_li:  # if name provided
                cv2.putText(img, nmSht_li[i], (5, 28), cv2.FONT_HERSHEY_SIMPLEX, fontScale, (0, 255, 0), 2)
            imgLs.append(img)

    arr_con = np.array(imgLs)
    img_grid = gallery(arr_con, ncols=len(idxLs))
    print('image saving to', os.path.join(gridFd, name + '.png'))
    cv2.imwrite(os.path.join(gridFd, name+'.png'), img_grid)

    if if_show:  # better not call this for batch operation, only for demo
        cv2.imshow('grid images', img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

def gallery(array, ncols=3):
    nindex, height, width = array.shape[:3]
    shp = array.shape
    if len(shp)>3:
        if_clr = True
        intensity = shp[3]
    else:
        if_clr = False
    nrows = nindex//ncols
    assert nindex == nrows*ncols
    # want result.shape = (height*nrows, width*ncols, intensity)
    # shp_new = [nrows,ncols, height, width] + shp[3:]
    if if_clr:
        result = (array.reshape(nrows, ncols, height, width, intensity)
              .swapaxes(1,2)
              .reshape(height*nrows, width*ncols, intensity))
    else:
        result = (array.reshape(nrows, ncols, height, width)
                  .swapaxes(1, 2)
                  .reshape(height * nrows, width * ncols))
    return result


def genPTr_dict(subj_li, mod_li, dsFd=r'G:\My Drive\ACLab Shared GDrive\datasetPM\danaLab'):
    '''
    loop idx_li, loop mod_li then generate dictionary {mod[0]:PTr_li[...], mod[1]:PTr_li[...]}
    :param subj_li:
    :param mod_li:
    :return:
    '''
    PTr_dct_li_src = {}  # a dict
    for modNm in mod_li:  # initialize the dict_li
        if not 'PM' in modNm:  # all PM immue
            PTr_dct_li_src[modNm] = []  # make empty list  {md:[], md2:[]...}
    for i in subj_li:
        for mod in mod_li:  # add mod PTr
            if not 'PM' in mod:  # not PTr for 'PM'
                if 'IR' in mod:
                    nm_mod_PTr = 'IR'
                elif 'depth' in mod:
                    nm_mod_PTr = 'depth'
                elif 'RGB' in mod:
                    nm_mod_PTr = 'RGB'
                else:
                    print('no such modality', mod)
                    exit(-1)
                pth_PTr = os.path.join(dsFd, '{:05d}'.format(i + 1), 'align_PTr_{}.npy'.format(nm_mod_PTr))
                PTr = np.load(pth_PTr)
                PTr_dct_li_src[mod].append(PTr)
    return PTr_dct_li_src
