% Gnerate a new uncertain shape and lookup similar items in the database
data_dir = 'data/brown_dataset/test';
shape_index = 8576;
shape_names = {'mandolin'};
grip_scales = {0.4};
tsdf_thresh = 10;
padding = 5;
scale = 4;

caltech_data = load('data/caltech/caltech101_silhouettes_28.mat');
num_points = size(caltech_data.X, 2);
data_dim = sqrt(num_points);

fprintf('Shape type: %s\n', caltech_data.classnames{caltech_data.Y(shape_index)});

%% load database into memtory
model_dir = 'data/grasp_transfer_models/brown_dataset';
downsample = 4;

% load models
filenames_filename = sprintf('%s/filenames.mat', model_dir);
tsdf_filename = sprintf('%s/tsdf_vectors_%d.mat', model_dir, downsample);
kd_tree_filename = sprintf('%s/kd_tree_%d.mat', model_dir, downsample);
grasps_filename = sprintf('%s/grasps_%d.mat', model_dir, downsample);
grasp_q_filename = sprintf('%s/grasp_q_%d.mat', model_dir, downsample);

S = load(filenames_filename);
filenames = S.filenames;

S = load(tsdf_filename);
tsdf_vectors = S.X;

S = load(kd_tree_filename);
kd_tree = S.kd_tree;

S = load(grasps_filename);
grasps = S.grasps;

S = load(grasp_q_filename);
grasp_q = S.grasp_qualities;

num_training = size(tsdf_vectors, 1);
num_points = size(tsdf_vectors, 2);
grid_dim = sqrt(num_points);

%% construct gpis
noise_scale = 0.1;
win = 7;
sigma = sqrt(2)^2;
h = fspecial('gaussian', win, sigma);
vis_std = false;

outside_mask = caltech_data.X(shape_index,:);
outside_mask = reshape(outside_mask, [data_dim, data_dim]);
M = ones(data_dim+2*padding);
M(padding+1:padding+size(outside_mask,1), ...
  padding+1:padding+size(outside_mask,2)) = outside_mask;
outside_mask = M;
outside_mask = imresize(outside_mask, (double(grid_dim) / size(M,1)));
outside_mask = outside_mask > 0.5;
tsdf = trunc_signed_distance(1-outside_mask, tsdf_thresh);

tsdf = standardize_tsdf(tsdf, vis_std);
tsdf = imfilter(tsdf, h);

% quadtree
min_dim = 2;
max_dim = 128;
inside_mask = tsdf < 0;
outside_mask = tsdf > 0;

% get surface points
SE = strel('square', 3);
outside_di = imdilate(outside_mask, SE);
outside_mask_di = (outside_di== 1);
tsdf_surface = double(outside_mask_di & inside_mask);
tsdf_surf_points = find(tsdf_surface(:) == 1);

dim_diff = max_dim - grid_dim;
pad = floor(dim_diff / 2);
outside_mask_padded = ones(max_dim);
outside_mask_padded(pad+1:grid_dim+pad, ...
    pad+1:grid_dim+pad) = outside_mask;
S = qtdecomp(outside_mask_padded, 0.1, [min_dim, max_dim]);
blocks = repmat(uint8(0),size(S)); 

for dim = [2048 1024 512 256 128 64 32 16 8 4 2 1];    
  numblocks = length(find(S==dim));    
  if (numblocks > 0)        
    values = repmat(uint8(1),[dim dim numblocks]);
    values(2:dim,2:dim,:) = 0;
    blocks = qtsetblk(blocks,S,dim,values);
  end
end

blocks(end,1:end) = 1;
blocks(1:end,end) = 1;

% parse cell centers
[X, Y] = find(S > 0);
num_cells = size(X, 1);
cell_centers = zeros(2, num_cells);

for i = 1:num_cells
   p = [Y(i); X(i)];
   cell_size = S(p(1), p(2));
   cell_center = p + floor(cell_size / 2) * ones(2,1);
   cell_centers(:, i) = cell_center;
end

% trim cell centers, add noise
%% variance parameters
var_params = struct();
var_params.y_thresh1_low = 79;
var_params.y_thresh1_high = 79;
var_params.x_thresh1_low = 79;
var_params.x_thresh1_high = 79;

var_params.y_thresh2_low = 79;
var_params.y_thresh2_high = 79;
var_params.x_thresh2_low = 79;
var_params.x_thresh2_high = 79;

var_params.y_thresh3_low = 79;
var_params.y_thresh3_high = 79;
var_params.x_thresh3_low = 79;
var_params.x_thresh3_high = 79;

var_params.occ_y_thresh1_low = 1;
var_params.occ_y_thresh1_high = 30;
var_params.occ_x_thresh1_low = 1;
var_params.occ_x_thresh1_high = 79;

var_params.occ_y_thresh2_low = 79;
var_params.occ_y_thresh2_high = 79;
var_params.occ_x_thresh2_low = 79;
var_params.occ_x_thresh2_high = 79;

var_params.transp_y_thresh1_low = 79;
var_params.transp_y_thresh1_high = 79;
var_params.transp_x_thresh1_low = 79;
var_params.transp_x_thresh1_high = 79;

var_params.transp_y_thresh2_low = 79;
var_params.transp_y_thresh2_high = 79;
var_params.transp_x_thresh2_low = 79;
var_params.transp_x_thresh2_high = 79;

var_params.occlusionScale = 1000;
var_params.transpScale = 4.0;
var_params.noiseScale = 0.1;
var_params.interiorRate = 0.1;
var_params.specularNoise = true;
var_params.sparsityRate = 0.2;
var_params.sparseScaling = 1000;
var_params.edgeWin = 1;

var_params.noiseGradMode = 'None';
var_params.horizScale = 1;
var_params.vertScale = 1;

cell_centers_mod = cell_centers - pad;
cell_centers_mod(cell_centers_mod < 1) = 1;
cell_centers_mod(cell_centers_mod > grid_dim) = grid_dim; 
cell_centers_linear = cell_centers_mod(2,:)' + ...
    (cell_centers_mod(1,:)' - 1) * grid_dim;     
num_centers = size(cell_centers_mod, 2);
noise = zeros(num_centers, 1);
measured_tsdf = tsdf(cell_centers_linear);

for k = 1:num_centers
    i = cell_centers_mod(1,k);
    j = cell_centers_mod(2,k);
    i_low = max(1,i-var_params.edgeWin);
    i_high = min(grid_dim,i+var_params.edgeWin);
    j_low = max(1,j-var_params.edgeWin);
    j_high = min(grid_dim,j+var_params.edgeWin);
    tsdf_win = tsdf(i_low:i_high, j_low:j_high);

    %fprintf('(i,j) = (%d,%d)\n', i, j);
    
    % add in transparency, occlusions
    if ((i > var_params.transp_y_thresh1_low && i <= var_params.transp_y_thresh1_high && ...
          j > var_params.transp_x_thresh1_low && j <= var_params.transp_x_thresh1_high) || ...
          (i > var_params.transp_y_thresh2_low && i <= var_params.transp_y_thresh2_high && ...
          j > var_params.transp_x_thresh2_low && j <= var_params.transp_x_thresh2_high) )
        % occluded regions
        if tsdf(i,j) < 0.6 % only add noise to ones that were actually in the shape
            measured_tsdf(k) = 0.5; % set outside shape
            noise(k) = var_params.transpScale; 
        end

    elseif tsdf(i,j) < 0.6 && ((i > var_params.y_thresh1_low && i <= var_params.y_thresh1_high && ...
            j > var_params.x_thresh1_low && j <= var_params.x_thresh1_high) || ...
            (i > var_params.y_thresh2_low && i <= var_params.y_thresh2_high && ... 
            j > var_params.x_thresh2_low && j <= var_params.x_thresh2_high) || ...
            (i > var_params.y_thresh3_low && i <= var_params.y_thresh3_high && ... 
            j > var_params.x_thresh3_low && j <= var_params.x_thresh3_high))

        noise(k) = var_params.occlusionScale;
    elseif ((i > var_params.occ_y_thresh1_low && i <= var_params.occ_y_thresh1_high && ...
            j > var_params.occ_x_thresh1_low && j <= var_params.occ_x_thresh1_high) || ... 
            (i > var_params.occ_y_thresh2_low && i <= var_params.occ_y_thresh2_high && ...
            j > var_params.occ_x_thresh2_low && j <= var_params.occ_x_thresh2_high) )
        % occluded regions
        noise(k) = var_params.occlusionScale;

    elseif tsdf(i,j) < -0.5 % only use a few interior points (since realistically we wouldn't measure them)
        if rand() > (1-var_params.interiorRate)
           noise(k) = var_params.noiseScale;
        else
           noise(k) = var_params.occlusionScale; 
        end
    else
        noise_val = 1; % scaling for noise

        % add specularity to surface
        if var_params.specularNoise && min(min(abs(tsdf_win))) < 0.6
            noise_val = rand();

            if rand() > (1-var_params.sparsityRate)
                noise_val = var_params.occlusionScale / var_params.noiseScale; % missing data not super noisy data
                %noiseVal = noiseVal * varParams.sparseScaling;
            end
        end
        noise(k) = noise_val * var_params.noiseScale;
    end
end

[Gx, Gy] = imgradientxy(tsdf, 'CentralDifference');
[X, Y] = meshgrid(1:grid_dim, 1:grid_dim);
%noise_grid = noise_scale * ones(grid_dim);

cell_normals = [Gx(cell_centers_linear), Gy(cell_centers_linear)];
cell_points = [X(cell_centers_linear), Y(cell_centers_linear)];
valid_indices = find(noise < var_params.occlusionScale);

shape_params = struct();
shape_params.gridDim = grid_dim;
shape_params.tsdf = measured_tsdf(valid_indices);
shape_params.normals = cell_normals(valid_indices,:);
shape_params.points = cell_points(valid_indices,:);
shape_params.noise = noise(valid_indices);%noise_grid(:);
shape_params.all_points = [X(:) Y(:)];
shape_params.fullTsdf = tsdf(:);
shape_params.fullNormals = [Gx(:) Gy(:)];
shape_params.com = mean(shape_params.points(shape_params.tsdf < 0,:));

figure(11);
scatter(shape_params.points(:,1), shape_params.points(:,2));
set(gca,'YDir','Reverse');

training_params = struct();
training_params.activeSetMethod = 'Full';
training_params.activeSetSize = 1;
training_params.beta = 10;
training_params.firstIndex = 150;
training_params.numIters = 0;
training_params.eps = 1e-2;
training_params.delta = 1e-2;
training_params.levelSet = 0;
training_params.surfaceThresh = 0.1;
training_params.scale = scale;
training_params.numSamples = 20;
training_params.trainHyp = false;
training_params.hyp = struct();
training_params.hyp.cov = [log(exp(2)), log(1)];
training_params.hyp.mean = [0; 0; 0];
training_params.hyp.lik = log(0.1);
training_params.useGradients = true;

num_samples = 1;
scale = 1.0;
[gp_model, shape_samples, construction_results] = ...
            construct_and_save_gpis(shape_names{1}, data_dir, shape_params, ...
                                    training_params, num_samples, scale);
        

%% lookup nearest neighbors
K = 16;
idx = knnsearch(kd_tree, tsdf(:)', 'K', K);

figure(66);
imshow(tsdf);
title('Original TSDF');

figure(77);
grasp = zeros(4,1);
%g2 = zeros(2,1);
for i = 1:K
   tsdf_neighbor = tsdf_vectors(idx(i),:);
   grasps_neighbor = grasps(idx(i), :, :);
   tsdf_neighbor = reshape(tsdf_neighbor, [grid_dim, grid_dim]);
   subplot(sqrt(K),sqrt(K),i);
   %imshow(tsdf_neighbor);
   %hold on;
   grasp(:) = grasps_neighbor(1,1,:);
%    g1(:) = grasp(1,1,1:2);
%    g2(:) = grasp(1,1,3:4);
   shape_params = tsdf_to_shape_params(tsdf);
   shape_params.surfaceThresh = 0.1;
   %plot_grasp_arrows(tsdf_neighbor, g1, g2, -grasp_dir, grasp_dir, 1, 5, [0;0], 3);
   visualize_grasp(grasp, shape_params, tsdf_neighbor, 1.0, 10, 3, grid_dim);
   title(sprintf('Neighbor %d', i));
end