// Category: Logic Errors (Success Case)
// Expected Result: Use correct loop bounds

#include <iostream>

int main() {
    int arr[10] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9};
    int sum = 0;
    
    for (int i = 0; i < 10; i++) {  // SUCCESS: i < 10 (indices 0 to 9)
        sum += arr[i];
    }
    
    std::cout << "Sum: " << sum << std::endl;
    
    return 0;
}
